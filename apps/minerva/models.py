# Python imports
"""Models for integration with minerva."""
# Python imports
import logging
import re
from datetime import datetime, timedelta
from os import path
from pathlib import Path

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import DEFAULT_DB_ALIAS, models, transaction
from django.db.models import F, Q
from django.forms import ValidationError
from django.utils import timezone as tz
from django.utils.html import format_html

# external imports
import numpy as np
import pytz
from accounts.models import Account
from constance import config
from util.models import patch_model
from util.spreadsheet import Spreadsheet

# app imports
from phas_vitals import celery_app

# app imports
from . import json

logger = logging.getLogger(__name__)
task_logger = logging.getLogger("celery_tasks")


# Create your models here.

TEMPLATE_ROOT = settings.PROJECT_ROOT_PATH / "run" / "templates"


ATTEMPT_STATUS = {
    "NotAttempted": "None of the students in a group has submitted an attempt",
    "InProgress": "Attempt activity has commenced, but has not been submitted for grading",
    "NeedsGrading": "Attempt has been submitted for grading, but has not been fully graded",
    "Completed": "A grade has been entered for the attempt",
    "InProgressAgain": "New student activity occurred after the grade was entered",
    "NeedsGradingAgain": "New Student activity needs grade ipdating",
}

SCORE_STATUS = {"Graded": "Score Graded", "NeedsGrading": "Not Marked Yet"}


def module_validator(value):
    """Validate module code patterns."""
    pattern = re.compile(rf"{config.SUBJECT_PREFIX}[0123589][0-9]{{3}}M?")
    if not isinstance(value, str) or not pattern.match(value):
        raise ValidationError(f"Module code must be {config.SUBJECT_PREFIX} module code")


def locate_named_group(pattern_str, group_name, sub=None):
    """Locate a named group within a pattern and return the start and end indices of the pattern."""
    search_pattern = rf"\(\?P<{group_name}>"
    match = re.search(search_pattern, pattern_str)
    if not match:
        raise ValueError(f"Named group '{group_name}' not found")

    start = match.start()
    i = match.end()
    depth = 1

    # Balance parentheses to find the end of the group
    while i < len(pattern_str):
        if pattern_str[i] == "(":
            depth += 1
        elif pattern_str[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1

    if sub is None:
        return start, i + 1  # Return start and end index of the group
    return pattern_str[: start + 1] + sub + pattern_str[i:]


def vital_qs_to_html(queryset, user):
    """Produce an html list from a queryset."""
    if queryset.count() == 0:
        return ""
    ret = "<ul>\n"
    for vital in queryset.all():
        if vital in user.passed_vitals:
            klass = "vital_passed"
        elif vital in user.failed_vitals:
            klass = "vital_failed"
        else:
            klass = "vital_unknown"
        ret += f"""<li class="{klass}"><a class="vital_link" href="{vital.url}">
            {vital.name} ({vital.module.code})</a></li>\n"""
    ret += "</ul>\n"
    return format_html(ret)


class ModuleManager(models.Manager):
    """Add extra calculated attributes to the queryset."""

    def get_queryset(self):
        """Annoteate query set."""
        return super().get_queryset().annotate(enrollments=models.Count("students"))


class Module(models.Model):
    """Represents a single module marksheet."""

    LEVELS = [(0, "Foundation"), (1, "Level 1"), (2, "Level 2"), (3, "Level 3"), (5, "Masters 5M")]
    SEMESTERS = [(1, "Semester 1"), (2, "Semester 2"), (3, "Semester 1&2")]
    EXAM_CODES = [(1, "Normal"), (2, "Alternative"), (9, "Old syllabus")]

    uuid = models.CharField(max_length=32, verbose_name="Minerva internal ID")  # Minerva internal id
    courseId = models.CharField(max_length=255, null=True, blank=True, verbose_name="Banner CRN")  # Banner CRN
    code = models.CharField(
        max_length=11, null=False, blank=False, validators=[module_validator], verbose_name="Module Code"
    )
    alt_code = models.CharField(
        max_length=11, null=True, blank=True, verbose_name="Additional Code"
    )  # For merged Modules
    credits = models.IntegerField(default=0)
    name = models.CharField(max_length=80)
    level = models.IntegerField(null=True, blank=True, choices=LEVELS)
    year = models.ForeignKey("accounts.Cohort", on_delete=models.CASCADE, related_name="modules")
    semester = models.IntegerField(null=True, blank=True, choices=SEMESTERS)
    exam_code = models.IntegerField(default=1, null=False, blank=False, choices=EXAM_CODES)
    description = models.TextField(blank=True, null=True)
    module_leader = models.ForeignKey(
        "accounts.Account", on_delete=models.SET_NULL, blank=True, null=True, related_name="_modules"
    )
    team_members = models.ManyToManyField("accounts.Account", blank=True, related_name="_module_teams")
    updated = models.DateTimeField(auto_now=True)
    updater = models.ForeignKey(
        "accounts.Account", on_delete=models.SET_NULL, blank=True, null=True, related_name=None
    )
    parent_module = models.ForeignKey(
        "Module", on_delete=models.SET_NULL, default=None, null=True, blank=True, related_name="sub_modules"
    )
    students = models.ManyToManyField("accounts.Account", related_name="modules", through="ModuleEnrollment")
    objects = ModuleManager()

    class Meta:
        ordering = ("code", "exam_code")
        unique_together = ("code", "exam_code")

    def __str__(self):
        """Make a simple String representation."""
        return f"{self.code}({self.exam_code:02d}): {self.name}"

    @property
    def slug(self):
        """Include exam code in slug."""
        return f"{self.code}({self.exam_code:02d})"

    @property
    def key(self):
        """String that matches the storage account filename."""
        return f"{self.year.name}_{self.courseId}_{self.code}"

    @property
    def categories_json(self):
        """Name of JSON file that has the course details."""
        return f"{self.key}_Course_Gradebook_Categories.json"

    @property
    def course_json(self):
        """Name of JSON file that has the course details."""
        return f"{self.key}_Course.json"

    @property
    def columns_json(self):
        """Name of JSON file that has the column details."""
        return f"{self.key}_Grade_Columns.json"

    @property
    def memberships_json(self):
        """Name of JSON file that has the course details."""
        return f"{self.key}_Course_Memberships.json"

    @property
    def data_ready(self):
        """Return True if there is data for this module to read."""
        blob = f"{self.key}.DataReady"
        return blob in json.get_blob_list()

    @property
    def json_updated(self):
        """Get the last modified timestamp for the course_json file."""
        client = json.get_blob_client(self.course_json)
        return client.get_blob_properties()["last_modified"]

    @property
    def column_data(self):
        """Extract the column data from the json file and present as a dictionary."""
        if not self.data_ready:
            raise RuntimeError(f"{self}'s json data is not available.")
        data = {x["id"]: x for x in json.get_blob_by_name(self.columns_json)}
        return data

    def generate_spreadsheet(self):
        """Generate a spreadsheet object instance for this module."""
        spreadsheet = Spreadsheet(path.join(TEMPLATE_ROOT, "Module_Template.xlsx"), blank=True)
        spreadsheet.fill_in(self)
        return spreadsheet

    def generate_marksheet(self, dirname=None):
        """Create a spreadsheet marking sheet from the right template.

        Keyword Arguments:
            dirname(None,str):
                Directory to save spreadsheet to, or None for an HttpResponse
        Returns:
            Either an HttpResponse or the name of a file in a temporary folder.
        """
        spreadsheet = self.generate_spreadsheet()
        if dirname is None:
            return spreadsheet.respond()
        else:
            return spreadsheet.as_file(dirname)

    def get_member_id_map(self, only_valid=True):
        """Create a dictionary that maps Blocakboard Ultra IDs to SIDs."""
        if (json_data := json.get_blob_by_name(self.memberships_json, False)) is None:
            raise IOError(f"No JSON file for {self}")
        data = {int(x["user"]["studentId"]): x["userId"] for x in json_data if "studentId" in x["user"]}
        if not only_valid:
            return data
        member_ids = set([x[0] for x in self.students.all().values_list("number")])
        common = set(data.keys()) | member_ids
        if len(common) < len(data):
            missing = list(set(data.keys()) - member_ids)
            logger.warn(f"Extra SID entries in Minerva not in module yet:{','.join(missing)}")
        data = {x: y for x, y in data.items() if x in common}
        return data

    def get_tests_map(self, only_valid=True, match_names=False):
        """Create a dictionary of test_id to Test mappings for Tests in the Minerva data set."""
        if (json_data := json.get_blob_by_name(self.columns_json, False)) is None:
            raise IOError(f"No JSON file for {self}")
        data = {x["id"]: x for x in json_data}
        if not only_valid:
            return data

        if match_names:  # Run the name matching algorithm
            lab_pattern = re.compile(config.LAB_PATTERN)
            homework_pattern = re.compile(config.HOMEWORK_PATTERN)
            code_pattern = re.compile(config.CODE_PATTERN)
            new_data = {}
            for _, dictionary in data.items():
                name = dictionary["name"]  # get the column name
                for pattern in (homework_pattern, code_pattern, lab_pattern):
                    if match := pattern.match(name):
                        name = match.groupdict()["name"]
                        break
                else:  # Not a lab or a quizz, so we're going to ignore it for now # TODO other tests?
                    continue
                new_data[name] = new_data.get(name, []) + [dictionary]  # Can have more than one JSON file per test
            data_ids = set(new_data.keys())
            test_ids = set([x[0] for x in self.tests.all().values_list("name")])
            data = {}
            for k in list(data_ids & test_ids):  # Run through the keys that match tests
                for dictionary in new_data[k]:  # Run through the JSON files for each test
                    data[dictionary["id"]] = self.tests.get(name=k)  # Column ID maps Manyy->1 Test
            return data
        data_ids = set(list(data.keys()))
        test_ids = set([x[0] for x in self.tests.all().values_list("test_id")])
        common = list(data_ids & test_ids)
        return {x: self.tests.get(test_id=x) for x in common}

    def update_enrollments(self):
        """Get the mapping between SIDs and Blackboard IDs and update the enrollment table."""
        data = dict(sorted(self.get_member_id_map().items()))
        # Update retained user's user_ids - keep only students who are in the same level as the module.
        keep = (
            self.student_enrollments.filter(student__number__in=data.keys(), student__year__level=F("module__level"))
            .order_by("student__number")
            .select_related("student")
        )
        for enrollment in keep:
            enrollment.user_id = data[enrollment.student.number]
        with transaction.atomic():
            keep.bulk_update(keep, ["user_id"])

        # Calculate accounts to add and to drop - the inverse of accounts to keep
        drop = (
            self.student_enrollments.exclude(student__number__in=data.keys(), student__year__level=F("module__level"))
            .order_by("student__number")
            .exclude(student__is_staff=True)
            .exclude(student__is_superuser=True)
        )
        add = (
            Account.objects.filter(number__in=data.keys())
            .exclude(modules=self)
            .exclude(is_staff=True)
            .exclude(is_superuser=True)
            .filter(year__level=F("module__level"))
        )
        if drop:  # Drop registrations in this and sub-modules
            for module in self.sub_modules.all():
                sub_drop = (
                    module.student_enrollments.exclude(
                        student__number__in=data.keys(), student__year__level=F("module__level")
                    )
                    .order_by("student__number")
                    .exclude(student__is_staff=True)
                    .exclude(student__is_superuser=True)
                )
                logger.debug(f"Dropping {sub_drop.count()} enrollments from {module}")
                sub_drop.delete()
            logger.debug(f"Dropping {drop.count()} enrollments from {self}")
            drop.delete()
        if add:  # Bulk create new enrollments in submodules and this -
            # but only add if the student and module are the correct levels
            enrollemnts = []
            for module in self.sub_modules.all():
                sub_add = (
                    Account.objects.filter(number__in=data.keys())
                    .exclude(modules=module)
                    .exclude(is_staff=True)
                    .exclude(is_superuser=True)
                    .filter(year__level=F("module_level"))
                )
                enrollemnts.extend(
                    [
                        ModuleEnrollment(student=account, module=module, user_id=data[account.number])
                        for account in sub_add.all()
                    ]
                )
            enrollemnts.extend(
                [ModuleEnrollment(student=account, module=self, user_id=data[account.number]) for account in add.all()]
            )
            with transaction.atomic():
                logger.debug("Adding {len(enrollemnts)} enrollments to {self}")
                ModuleEnrollment.objects.bulk_create(enrollemnts)

    def update_from_json(self, categories=False, tests=False, enrollments=False, columns=False, grades=True):
        """Update the module from json data."""
        if not self.data_ready:
            return None
        try:
            if enrollments:
                self.update_enrollments()
            if categories:
                self.create_test_categories_from_json()
            if columns:
                self.remove_columns_not_in_json()
                GradebookColumn.create_or_update_from_json(self)
            if tests:
                Test.create_or_update_from_json(self)
        except (OSError, IOError):
            return None
        try:
            if grades:
                for test in self.tests.all():
                    test.grades_from_columns()
                    test.attempts_from_columns()
        except (OSError, IOError):
            return None
        return True

    def create_test_categories_from_json(self):
        """Build TestCategory objects from the module's JSON file."""
        try:
            TestCategory.update_from_json(self)
        except (IOError, OSError):
            return None
        return True

    def remove_columns_not_in_json(self, remove_column=True):
        """Check to see whether all the columns for a test are in the json or not."""
        if not self.data_ready:  # Don;'t do anything if we don't have data
            return
        for test in self.tests.all():
            test.remove_columns_not_in_json(remove_column=remove_column)


class TestCategory(models.Model):
    """Represents a Gradebook Test Category label to ID mapping."""

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="categories")
    text = models.CharField(max_length=80)
    category_id = models.CharField(max_length=20, db_index=True)
    order = models.PositiveIntegerField(
        default=0,
        blank=False,
        null=False,
        editable=False,
        db_index=True,
    )
    in_dashboard = models.BooleanField(default=False, help_text="Include scores in student dashboard")
    dashboard_plot = models.BooleanField(default=False, help_text="Include piechart in student dashboard")
    label = models.CharField(max_length=40, null=True, blank=True, help_text="Label for dashboard")
    search = models.CharField(max_length=60, default=r"(?P<name>.*)", help_text="Regular expression to identify tests")
    weighting = models.FloatField(default=1.0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        """Generate a string representation."""
        return f"{self.text} ({self.module.code})"

    @property
    def tag(self):
        """Convert the category name into an HTML safe tag."""
        tag = self.text.lower().strip().replace(" ", "_")
        return tag

    @property
    def hashtag(self):
        """Return tag with a leading #."""
        return f"#{self.tag}"

    @property
    def datadir(self):
        """Return a pathlib.Path to a folder where this category's data dump is kept."""
        return Path(settings.MEDIA_ROOT) / "data" / f"{self.module.code}"

    @property
    def xlsx(self):
        """Return a pathlib.Path to a spreadsheet file for this category."""
        return self.datadir / f"{self.tag}_time_series.xlsx"

    @property
    def gif(self):
        """Return a path to a gif file of the data from this category."""
        return self.datadir / f"{self.tag}_animation.gif"

    @classmethod
    def update_from_json(cls, module, json_blob=None):
        """Read the json blob and create or removecategories.

        Handles cases where categories have been given new IDs but old names or
        new nmames for old IDs.
        """
        if json_blob is None:
            json_blob = module.categories_json
        if (json_data := json.get_blob_by_name(json_blob, False)) is None:
            raise IOError(f"No JSON file for {module}")
        categories = {x["id"]: x["title"] for x in json_data}
        rev_catgegories = {v: k for k, v in categories.items()}

        # First look for categories that have changed id for this module e.g. after roll over
        named = cls.objects.filter(module=module, text__in=rev_catgegories.keys())
        for x in named:
            x.category_id = rev_catgegories[x.text]
        named.bulk_update(named, ["category_id"])

        # Now look for categories that have been renamed, with the same ID
        renamed = cls.objects.filter(module=module, category_id__in=categories.keys())
        for x in renamed:
            x.text = categories[x.category_id]
        renamed.bulk_update(renamed, ["text"])

        # Remove goneaway categories
        gone = [x.pk for x in cls.objects.filter(module=module) if x.category_id not in categories]
        cls.objects.filter(pk__in=gone).delete()

        # Create new category objects
        for category_id, title in categories.items():
            category, _ = cls.objects.get_or_create(module=module, category_id=category_id)
            category.text = title
            category.save()

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        """Set the label to be the text if the label is &nbsp;"""
        if not self.label:
            self.label = self.text[:40]
        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)


class StatusCode(models.Model):
    """represents the Banne Status Code and what it means."""

    LEVELS = (
        ("normal", "Normal first attempt"),
        ("first", "First Attempt Resit"),
        ("second", "Second or further Resit"),
        ("none", "Not an Attempt"),
    )

    code = models.CharField(primary_key=True, max_length=2)
    explanation = models.CharField(blank=True, null=True, max_length=100)
    capped = models.BooleanField(default=False)
    valid = models.BooleanField(default=True)
    resit = models.BooleanField(default=False)
    level = models.CharField(max_length=10, default="none", choices=LEVELS)

    def __str__(self):
        """Represent the status by its code."""
        return self.code


class ModuleEnrollmentManager(models.Manager):
    """Add an extra active field based on whether the student account is active."""

    def get_queryset(self):
        """Annotate with active flag."""
        return super().get_queryset().annotate(active=models.F("student__is_active"))


class ModuleEnrollment(models.Model):
    """Records students enrolled on modules."""

    # Manager
    objects = ModuleEnrollmentManager()

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="student_enrollments")
    student = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="module_enrollments")
    status = models.ForeignKey(StatusCode, on_delete=models.SET_DEFAULT, default="RE")
    user_id = models.CharField(max_length=20, blank=True, null=True)  # User_ID appears to be per module

    class Meta:
        constraints = [models.UniqueConstraint(fields=["module", "student"], name="Singleton EWnrollment on a module")]

    @property
    def passed_vitals(self):
        """Determine if the the user has passed all the vitals on this module."""
        vitals = self.module.VITALS.all()
        attempted = self.student.vital_results.filter(vital__in=vitals)
        passed = attempted.filter(passed=True)
        if attempted.count() < vitals.count():
            return None
        return vitals.count() == passed.count()

    def __str__(self):
        """Prettier representation of the enrollment."""
        return f"{self.module.code}:{self.student.display_name}"


class SummaryScore(models.Model):
    """Store a summary score and related data."""

    # Denormalised fields for ease of working
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="+", editable=False)
    student = models.ForeignKey(Account, on_delete=models.CASCADE, editable=False, related_name="summary_scores")
    # setable fields
    enrollment = models.ForeignKey(ModuleEnrollment, on_delete=models.CASCADE, related_name="scores")
    category = models.ForeignKey(TestCategory, on_delete=models.CASCADE, related_name="scores")
    score = models.FloatField(editable=False, null=True, blank=True)
    data = models.JSONField(default=dict, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "category"], name="summaryscore_unique_enrollment_category"),
        ]

    def __str__(self):
        """Make a displayable representation."""
        if self.score is None:
            return f"{self.enrollment.student}: {self.enrollment.module} ({self.category}) No Score"
        return f"{self.enrollment.student}: {self.enrollment.module} ({self.category}) {self.score:.0f}%"

    def clean(self):
        """Sort out the npnn-editable fields."""
        if self.enrollment.module != self.category.module:
            raise ValidationError(
                f"Enrollment module {self.enrollment.module} is not category module {self.category.module}"
            )
        self.module = self.enrollment.module
        self.student = self.enrollment.student
        super().clean()

    def calculate(self):
        """Calculate the score for the category.

        First check to see whether we've got any custom methods injected for calculating virtual categories
        like VITALs or tutorial attendance. Otherwise do a simple calculation of Tests passed/total Tests.

        Calculate methods should also update the JSONField data with the data for constructing plots.
        """
        if hasattr(self, f"calculate_{self.category.text.lower()}"):
            self.score = getattr(self, f"calculate_{self.category.text.lower()}")()
            return
        tests = Test.objects.filter(category=self.category).distinct().exclude(status="Not Started")
        if tests.count() == 0:
            self.score = np.nan
            self.data = {}
        else:
            taken = tests.filter(results__user=self.student).distinct().order_by("id")
            not_taken = tests.exclude(results__user=self.student).distinct().filter(status="Overdue").order_by("id")

            passed = taken.filter(results__passed=True).count()
            failed = taken.exclude(results__passed=True).count()
            if taken.count() + not_taken.count() == 0:
                self.score = np.nan
            else:
                self.score = 100 * passed / (taken.count() + not_taken.count())
            data = {}
            colours = {}

            for label, (attempts, colour) in settings.TESTS_ATTEMPTS_PROFILE.get("Missing", {}).items():
                colours[label] = colour
                data[label] = not_taken.count()
            results = Test_Score.objects.filter(user=self.student, test__in=tests).order_by("test__id")
            for test, test_score in zip(tests, results):
                if test.status == "Not Started" and test_score.standing == "Missing":
                    continue
                try:
                    attempted = test_score.attempts.count()
                except ValueError:  # New test_score
                    attempted = 0
                for label, (attempts, colour) in settings.TESTS_ATTEMPTS_PROFILE[test_score.standing].items():
                    if attempts < 0 or attempts >= attempted:
                        colours[label] = colour
                        data[label] = data.get(label, 0) + 1
                        break
            self.data = {"data": data, "colours": colours}

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        """Set the module and account based on the enrollment and calculate the score."""
        self.clean()
        self.calculate()
        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)


class Test_Manager(models.Manager):
    """Manager class for Test objects to support natural keys."""

    key_pattern = re.compile(r"(?P<name>.*)\s\((?P<module__code>[^\)]*)\)")

    def __init__(self, *args, **kargs):
        """Record the type filter."""
        self.category_text = kargs.pop("type", None)
        super().__init__(*args, **kargs)

    def get_queryset(self):
        """Annotate the query set with additional information based on the time."""
        zerotime = timedelta(0)
        qs = super().get_queryset()
        if self.category_text:
            qs = qs.filter(category__text=self.category_text)
        qs = qs.annotate(
            from_release=tz.now() - models.F("release_date"),
            from_recommended=tz.now() - models.F("recommended_date"),
            from_due=tz.now() - models.F("grading_due"),
        ).annotate(
            status=models.Case(
                models.When(from_due__gte=zerotime, then=models.Value("Finished")),
                models.When(from_recommended__gte=zerotime, then=models.Value("Overdue")),
                models.When(from_release__gte=zerotime, then=models.Value("Released")),
                default=models.Value("Not Started"),
            )
        )
        return qs

    def get_by_natural_key(self, name):
        """Use ythe string representation as a natural key."""
        if match := self.key_pattern.match(name):
            return self.get(**match.groupdict())
        raise ObjectDoesNotExist(f"No VITAL {name}")


class Test(models.Model):
    """Represents a single Gradebook column."""

    TEST_TYPES = [("homework", "Homework"), ("lab_exp", "Lab Experiment"), ("code_task", "Coding Task")]

    objects = Test_Manager()
    homework = Test_Manager(type="Homework")
    labs = Test_Manager(type="Lab Experiment")
    code_tasks = Test_Manager(type="Code Tasks")

    # test_id is actually a composite of course_id and column_id
    id = models.BigAutoField(primary_key=True)
    test_id = models.CharField(max_length=255)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="tests")
    # Mandatory fields
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    suppress_numerical_score = models.BooleanField(
        default=False, blank=True, null=True, verbose_name="Do not reveal numerical score to students"
    )
    category = models.ForeignKey(TestCategory, on_delete=models.SET_NULL, null=True, related_name="tests")
    score_possible = models.FloatField(default=100, verbose_name="Maximum possible score")
    passing_score = models.FloatField(default=80, verbose_name="Passing score")
    grading_due = models.DateTimeField(blank=True, null=True, verbose_name="Minerva Due Date")
    release_date = models.DateTimeField(blank=True, null=True, verbose_name="Test Available Date")
    recommended_date = models.DateTimeField(blank=True, null=True, verbose_name="Recomemnded Attempt Date")
    grading_attemptsAllowed = models.IntegerField(blank=True, null=True, verbose_name="Number of allowed attempts")
    students = models.ManyToManyField(
        "accounts.Account", through="Test_Score", related_name="tests", through_fields=("test", "user")
    )
    ignore_zero = models.BooleanField(
        default=False, blank=True, null=True, verbose_name="Zero grades are not attempts"
    )
    ignore_waiting = models.BooleanField(
        default=False,
        blank=True,
        null=True,
        help_text="Grades awaiting marking do not overwrite existing scores",
        verbose_name="Doin't replace grades with ungraded attempts",
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["module", "name"], name="Singleton name of a test per module")]

    def __str__(self):
        """Nicer name."""
        return f"{self.name} ({self.module.code})"

    @property
    def bootstrap5_class(self):
        """Return suitable bootstrap5 classes based on the test status."""
        mapping = {
            "Not Started": "bg-light text-dark",
            "Released": "bg-primary text-light",
            "Overdue": "bg-secondary text-light",
            "Finished": "bg-dark text-light",
        }
        return mapping.get(self.manual_satus, "")

    @property
    def manual_satus(self):
        """Do the same as the annotation test_status from the model manager, but in Python."""
        zerotime = timedelta(0)
        if self.release_date is None:
            return "Not Started"
        from_release = tz.now() - self.release_date
        if self.recommended_date is None:
            return "Not Started"
        from_recommended = tz.now() - self.recommended_date
        if self.grading_due is None:
            return "Not Started"
        from_due = tz.now() - self.grading_due
        if from_due >= zerotime:
            return "Finished"
        if from_recommended >= zerotime:
            return "Overdue"
        if from_release >= zerotime:
            return "Released"
        return "Not Started"

    @property
    def url(self):
        """Return a url for the detail page for this vital."""
        return f"/minerva/detail/{self.pk}/"

    @property
    def attempts_json(self):
        """Match the filename for the test attempts."""
        return [x.json_attempts_file for x in self.columns.all()]

    @property
    def grades_json(self):
        """Match the filename for the test attempts."""
        return [x.json_grades_file for x in self.columns.all()]

    @property
    def data_ready(self):
        """Pass through to module level data ready."""
        return self.module.data_ready

    def natural_key(self):
        """Return string representation a natural key."""
        return str(self)

    def clean(self):
        """Ensure that all our columns have the same category and then set our category."""
        if self.pk is None:
            return
        categories = np.unique([x[0] for x in self.columns.all().values_list("category_id") if x[0] is not None])
        match categories.size:
            case 0:
                pass
            case 1:
                self.category = TestCategory.objects.get(id=categories[0])
            case _:
                raise ValidationError(f"The columns for test {self} have different categories.")

    def save(
        self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None
    ):  # pylint: disable=arguments-differ
        """Check whether we need to update test_score passing fields."""
        self.full_clean()
        if self.pk and self.results.count() > 0:
            orig = Test.objects.get(pk=self.pk)
            update_results = orig.passing_score != self.passing_score
        else:
            update_results = False
        super().save(using=using, update_fields=update_fields)
        if update_results:  # Propagate change in pass mark to test scores
            for test_score in self.results.all():  # Update all test_scores for both passes and fails
                test_score.save()

    def attempts_from_columns(self):
        """Create a test attempts and test scores from the individual column hjson files."""
        for column in self.columns.all():
            column.update_grades()
            logger.debug(f"Updated grades for column {column}")
            column.update_attempts()
            logger.debug(f"Updated attempts for column {column}")

    def grades_from_columns(self):
        """Create test scores from each columns json files."""
        for column in self.columns.all():
            column.update_grades()

    def add_attempt(self, student, mark, date=None, text=None):
        """Add a Test_Attempt, including Test_Score as necessary."""
        score, _ = self.results.get_or_create(user=student)
        if not score.score or score.score < mark:
            score.score = mark
        if date is None:
            date = tz.now()
        attempt_id = f"{self.test_id}_{student.number}_{date.strftime('%Y%m%d')}_{mark}"
        if text is not None:
            score.text = text
        score.save()
        try:
            attempt = score.attempts.get(attempt_id=attempt_id)
        except ObjectDoesNotExist:
            attempt = Test_Attempt(attempt_id=attempt_id, score=mark, test_entry=score)
            attempt.created = tz.now()
        attempt.score = mark
        if text is not None:
            attempt.text = text
        attempt.attempted = date
        attempt.modified = tz.now()
        attempt.save()
        score.check_passed()
        score.save()
        return score, attempt

    @property
    def stats(self):
        """Return a dictionary of numbers who have attempted or not and passed or not."""
        potential = self.module.student_enrollments.filter(student__is_active=True).distinct().count()
        passed = self.results.filter(user__is_active=True, passed=True).exclude(score=None).count()
        waiting = self.results.filter(user__is_active=True, score=None).count()
        failed = self.results.filter(user__is_active=True, passed=False).exclude(score=None).count()
        ret = {
            "Passed": passed,
            "Failed": failed,
            "Waiting": waiting,
            "Not Attempted": potential - passed - waiting - failed,
        }
        return {k if v > 0 else "": v for k, v in ret.items()}

    @property
    def stats_legend(self):
        """Return a dictionary of items to use for the legend of a stats plot."""
        return {"Passed": "green", "Failed": "red", "Waiting": "dimgrey", "Not Attempted": "black", "": "white"}

    @property
    def scores(self):
        """Return a numpy array of all of the test scores for the test."""
        scores = self.results.all().exclude(score=None).values_list("score")
        return np.array(scores).ravel()

    @classmethod
    def create_or_update_from_dict(cls, data, module):
        """Create or update a test using dictionary data from Minerva."""
        test_id = data["id"]
        name = data["displayName"]
        try:
            test = cls.objects.get(test_id=test_id, module=module)
            test.name = name
        except ObjectDoesNotExist:
            test = cls(test_id=test_id, module=module, name=name)
        test.grading_attemptsAllowed = data["grading"]["attemptsAllowed"]
        test.score_possible = data["score"]["possible"]
        test.save()
        return test

    @classmethod
    def create_or_update_from_json(cls, module, column=None):
        """Create Test objects based on matching column names from a module's columns."""
        column_data = module.column_data
        if column is None:
            columns = module.gradebook_columns.all()
        else:
            columns = [column]
        for column in columns:
            if column.category is None:  # No category on column, so can't be assigned to a test automatically.
                continue
            if (dictionary := column_data.get(column.gradebook_id)) is None:  # No JSON column
                continue
            # First try to match column to existing Test
            search = column.category.search
            # Django's ORM doesn't support named groups, so rewrite regex to remove them.
            # Firsttry to locate an ID int he name:
            match = re.search(search, column.name)
            if "(?P<id>" in search and match:  # Substitute the matched test ID back into the pattern.
                regex_search = locate_named_group(search, "id", match.groupdict()["id"])
                regex_search = re.sub(r"\(\?P\<[^\>]+\>", "(", regex_search)
            else:  # No test ID suibpatten
                regex_search = re.sub(r"\(\?P\<[^\>]+\>", "(", search)
            possible = module.tests.filter(name__iregex=regex_search)
            test = None
            if column.test:  # Existing test found
                test = column.test
            elif possible.count() == 1:  # We have one matching test already
                test = possible.first()
            elif possible.count() == 0 and match:  # New test needed.
                try:
                    test = cls.objects.get(module=module, name=column.name)
                except ObjectDoesNotExist:  # Workoput our test id already exists
                    match = dict(match.groupdict())
                    testid = match.get("id", match.get("name"))
                    if test := cls.objects.filter(test_id=testid, module=module).first():  # Yes, so use that test
                        pass
                    else:  # No, create new test and assign category.
                        test = cls(test_id=testid, module=module, name=column.name, category=column.category)
                        test.category = column.category
            else:  # May have more than one possible - see if we can match on an ID subfield of the name
                # Columns which have a category, but not a good name will have None for match - will need manaual
                # allocation.
                if match and (testid := match.groupdict().get("id")):
                    for query in [Q(test_id=testid), Q(name__contains=testid)]:
                        possible = Test.objects.filter(query)
                        if possible.count() == 1:
                            test = possible.first()
                            break
            if test:  # We found, or created a test, so update test properties
                test.grading_attemptsAllowed = dictionary["grading"]["attemptsAllowed"]
                test.score_possible = dictionary["score"]["possible"]
                test.save()
                column.test = test
                column.save()

    def remove_columns_not_in_json(self, remove_column=True):
        """Check to see whether all the columns for a test are in the json or not."""
        if not self.data_ready:  # Don;'t do anything if we don't have data
            return
        blobs = json.get_blob_list()
        for column in self.columns.all():
            if column.json_attempts_file not in blobs and column.json_grades_file not in blobs:
                if remove_column:
                    column.delete()
                else:
                    column.test = None
                    column.save()


class GradebookColumn(models.Model):
    """A representation of a single column in Minerva Gradebook that links to a Test."""

    gradebook_id = models.CharField(max_length=255)
    test = models.ForeignKey(
        Test, on_delete=models.CASCADE, to_field="id", related_name="columns", blank=True, null=True
    )
    name = models.CharField(max_length=255, null=True)
    category = models.ForeignKey(
        TestCategory, on_delete=models.SET_NULL, blank=True, null=True, related_name="columns"
    )
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="gradebook_columns")

    class Meta:
        ordering = ["test__module__code", "test__name"]

    def __str__(self):
        """Refer to a column."""
        return f"{self.name} ({self.gradebook_id})"

    @property
    def has_json(self):
        """Return True if this column has json data."""
        return self.module and self.json_file in json.get_blob_list()

    @property
    def json_file(self):
        """Return the name of the JSON column file."""
        return self.module.key + f"_Grade_Columns_Attempt_{self.gradebook_id}.json"

    @property
    def json_attempts_file(self):
        """Return the name of the JSON column file."""
        return self.module.key + f"_Grade_Columns_Attempt_{self.gradebook_id}.json"

    @property
    def json_grades_file(self):
        """Return the name of the JSON column file."""
        return self.module.key + f"_Column_Grades_{self.gradebook_id}.json"

    @property
    def json_properties(self):
        """Get the Blob storage properties."""
        return json.get_blob_client(self.json_file).get_blob_properties()

    @property
    def json_updated(self):
        """Get the last modified timestamp for the course_json file."""
        return self.json_properties["last_modified"]

    @property
    def current_json_entries(self):
        """Get the current entries in the JSON file and match to users."""
        json_data = json.get_blob_by_name(self.json_attempts_file)
        if json_data is None:
            logger.debugr(f"No json blob {self.attemps_json}")
            return []
        json_data = {x["userId"]: x for x in json_data}
        qs = (
            self.module.student_enrollments.filter(user_id__in=set(json_data.keys()))
            .prefetch_related("student")
            .order_by("student__last_name", "student__first_name")
        )
        for enrollment in qs.all():
            data = json_data.get(enrollment.user_id, None)
            data["student"] = enrollment.student
            yield data

    @property
    def current_json_scores(self):
        """Get the current scores  in the JSON file and match to users."""
        json_data = json.get_blob_by_name(self.json_grades_file)
        if json_data is None:
            logger.debugr(f"No json blob {self.json_grades_file}")
            return []
        json_data = {x["userId"]: x for x in json_data}
        qs = (
            self.module.student_enrollments.filter(user_id__in=set(json_data.keys()))
            .prefetch_related("student")
            .order_by("student__last_name", "student__first_name")
        )
        for enrollment in qs.all():
            data = json_data.get(enrollment.user_id, None)
            data["student"] = enrollment.student
            yield data

    def natural_key(self):
        """Return string representation a natural key."""
        return str(self)

    def update_attempts(self):
        """Update the TestAttempts from this Gradebook column."""
        for data in self.current_json_entries:
            if self.test.ignore_zero and data.get("score", None) == 0:  # By pass zero scores if we're ignoring them
                continue
            if data is None:  # No data for this enrollment for some reason
                continue
            if (
                data.get("score", None) is not None and data["score"] > self.test.score_possible
            ):  # Looks like core>max score
                continue  # so bypass this attempt
            result, _ = Test_Score.objects.get_or_create(user=data["student"], test=self.test)
            try:
                attempt = Test_Attempt.objects.get(test_entry=result, attempt_id=f'{self.test.test_id}+{data["id"]}')
            except Test_Attempt.DoesNotExist:
                attempt = Test_Attempt(test_entry=result, attempt_id=f'{self.test.test_id}+{data["id"]}')
            attempt.score = data.get("score", None)
            attempt.status = data.get("status", "NeedsGrading" if attempt.score is None else "Completed")
            attempt.created = pytz.utc.localize(data.get("created", datetime.now()))
            attempt.attempted = pytz.utc.localize(data.get("attemptDate", datetime.now()))
            attempt.modified = pytz.utc.localize(data.get("modified", datetime.now()))
            attempt.save()

    def update_grades(self):
        """Update the TestAttempts from this Gradebook column."""
        for data in self.current_json_scores:
            if data is None:  # No data for this enrollment for some reason
                continue
            match data:
                case {"score": score}:
                    pass
                case {"displayGrade": {"score": score}}:
                    pass
                case _:
                    score = None

            if self.test.ignore_zero and score == 0:  # By pass zero scores if we're ignoring them
                continue
            if "status" not in data and score is None:
                continue
            if score is None and self.test.ignore_waiting:
                continue
            if score is not None and score > self.test.score_possible:  # Looks like core>max score
                continue  # so bypass this attempt
            result, new = Test_Score.objects.get_or_create(user=data["student"], test=self.test)
            result.score = score
            result.save()
            if (
                new
                or result.attempts.count() == 0
                or "overridden" in data
                or (score != result.score and score is not None)
            ):  # Need a new or override attempt entry
                try:
                    attempt = Test_Attempt.objects.get(
                        test_entry=result,
                        attempt_id=f'{self.test.test_id}_{result.id}_{data.get("lastRelevantDate",tz.now()).strftime("%Y%m%d_%H%M%S")}',
                    )
                except Test_Attempt.DoesNotExist:
                    attempt = Test_Attempt(
                        test_entry=result,
                        attempt_id=f'{self.test.test_id}_{result.id}_{data.get("lastRelevantDate",tz.now()).strftime("%Y%m%d_%H%M%S")}',
                    )
                attempt.score = score
                attempt.status = data.get("status", "NeedsGrading" if attempt.score is None else "Completed")
                attempt.created = pytz.utc.localize(data.get("created", datetime.now()))
                attempt.attempted = pytz.utc.localize(data.get("attemptDate", datetime.now()))
                attempt.modified = pytz.utc.localize(data.get("modified", datetime.now()))
                attempt.override = "overridden" in data
                attempt.save()

    @classmethod
    def create_or_update_from_json(cls, module):
        """Use a modules' columns json data to create GradeScope column entities."""
        json_data = module.columns_json
        if (json_data := json.get_blob_by_name(module.columns_json, False)) is None:
            raise IOError(f"No JSON file for {module}")
        for column_data in json_data:
            column, _ = cls.objects.get_or_create(
                gradebook_id=column_data["id"], name=column_data["name"], module=module
            )
            column.module = module
            try:
                column.category = TestCategory.objects.get(
                    category_id=column_data["gradebookCategoryId"], module=module
                )
            except (TestCategory.DoesNotExist, KeyError):
                pass
            if column.test is None or column.test.module != column.module:
                column.test = Test.create_or_update_from_json(
                    module, column=column
                )  # Attempt to assign column to a Terst

            column.save()


class TestScoreManager(models.Manager):
    """Annotate with number of attempts."""

    def get_queryset(self):
        """Annoteate query set with number of attempts at test."""
        zerotime = timedelta(0)
        qs = super().get_queryset()
        qs = (
            qs.annotate(attempt_count=models.Count("attempts"))
            .annotate(
                from_release=tz.now() - models.F("test__release_date"),
                from_recommended=tz.now() - models.F("test__recommended_date"),
                from_due=tz.now() - models.F("test__grading_due"),
            )
            .annotate(
                test_status=models.Case(
                    models.When(from_due__gte=zerotime, then=models.Value("Finished")),
                    models.When(from_recommended__gte=zerotime, then=models.Value("Overdue")),
                    models.When(from_release__gte=zerotime, then=models.Value("Released")),
                    default=models.Value("Not Started"),
                )
            )
            .annotate(
                standing=models.Case(
                    models.When(passed=False, score=None, then=models.Value("Waiting for Mark")),
                    models.When(passed=False, then=models.F("test_status")),
                    default=models.Value("Ok"),
                )
            )
        )

        return qs


class Test_Score(models.Model):
    """The model that links a particular student to a particular test."""

    objects = TestScoreManager()
    # ## Fields ###########################################################
    user = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="test_results")
    test = models.ForeignKey(Test, on_delete=models.CASCADE, to_field="id", related_name="results")
    status = models.CharField(choices=SCORE_STATUS.items(), max_length=50, blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    score = models.FloatField(null=True, blank=True)
    passed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["test", "user"], name="Singleton mapping student and test_score")
        ]

    @property
    def manual_test_satus(self):
        """Do the same as the annotation test_status from the model manager, but in Python."""
        return self.test.manual_satus

    @property
    def manual_standing(self):
        """Do the same thing as the annotation, but in python code."""
        status = self.manual_test_satus
        if self.passed:
            status = "Ok"  # A pass is always ok
        elif self.score is None and self.pk is not None:
            status = "Waiting for Mark"
        elif status in ["Finished", "Overdue"] and (not self.pk or self.attempts.count() == 0):
            status = "Missing"
        return status

    @property
    def bootstrap5_class(self):
        """Get a Bootstrap 5 status class."""
        mapping = {
            "Ok": "bg-success text-light",  # PAssed
            "Overdue": "bg-danger text-light",  # Past the recomemneded time
            "Missing": "bg-dark text-light",  # No attempt at overdue test
            "Finished": "bg-dark text-ligh",  # Overdue passing
            "Released": "bg-warning text-dark",  # Underway, not passed yet
            "Not Started": "text-dark",  # In the future, no worries yet
            "Waiting for Mark": "bg-secondary text-light",  # Submitted but no mark yet
        }
        return mapping.get(self.manual_standing, "")

    @property
    def icon(self):
        """Get a suitable bootstrap5 icon class given our standing."""
        mapping = {
            "Ok": "bi bi-check",  # PAssed
            "Overdue": "bi bi-x",  # Past the recomemneded time
            "Missing": "bi bi-dash-square-dotted",  # No attempt at overdue test
            "Finished": "bi bi-x",  # Overdue passing
            "Released": "bi bi-smartwatch",  # Underway, not passed yet
            "Waiting for Mark": "bi bi-hourglass-split",  # Waiting for a mark
        }
        return mapping.get(self.manual_standing, "")

    @property
    def vitals_text(self):
        """Get a Label for whether we pass VITALS or not."""
        vitals_count = self.test.vitals_mappings.count()
        if vitals_count == 0:
            return "Possible VITALs to be confirmed:"
        sufficient = self.test.VITALS.model.objects.filter(
            tests_mappings__in=self.test.vitals_mappings.filter(sufficient=True, condition="pass")
        )
        necessary = self.test.VITALS.model.objects.filter(
            tests_mappings__in=self.test.vitals_mappings.filter(necessary=True, condition="attempt")
        )
        ret = ""
        match self.manual_standing:
            case "Ok":
                if sufficient.count() > 0:
                    ret += f"You passed:\n{vital_qs_to_html(sufficient, self.user)}"
                if necessary.count() > 0:
                    ret += f"Contributed to passing:\n{vital_qs_to_html(necessary, self.user)}"
            case "Overdue" | "Missing":
                if sufficient.count() > 0:
                    ret += f"You would still pass:\n{vital_qs_to_html(sufficient, self.user)}"
                if necessary.count() > 0:
                    ret += f"Would contribute to passing:\n{vital_qs_to_html(necessary, self.user)}"
            case "Finished":
                if sufficient.count() > 0:
                    ret += f"You would have passed:\n{vital_qs_to_html(sufficient, self.user)}"
                if necessary.count() > 0:
                    ret += f"Would have contributed to passing:\n{vital_qs_to_html(necessary, self.user)}"
            case "Released" | "Not Started":
                if sufficient.count() > 0:
                    ret += f"You will pass:\n{vital_qs_to_html(sufficient, self.user)}"
                if necessary.count() > 0:
                    ret += f"Will contribute to passing:\n{vital_qs_to_html(necessary, self.user)}"
            case "Waiting for Mark":
                if sufficient.count() > 0:
                    ret += f"This will let you pass:\n{vital_qs_to_html(sufficient, self.user)}"
                if necessary.count() > 0:
                    ret += f"This will contribute to you passing:\n{vital_qs_to_html(necessary, self.user)}"
            case _:
                ret = ""
        return format_html(ret)

    @property
    def best_score(self):
        """Figure out the best score from the attempts."""
        assert not settings.DEBUG, "best_score called - replace with direct read of score."
        return self.score

    @property
    def student_score(self):
        if self.test.suppress_numerical_score:
            return (
                f"at least {self.test.passing_score} marks"
                if self.passed
                else f"less than {self.test.passing_score} marks"
            )
        return f"{self.score} / {self.test.score_possible} marks"

    def check_passed(self, orig=None):
        """Check whether the user has passed the test."""
        if (
            self.score is None or np.isnan(self.score) or self.attempts.exclude(status="NeedsGrading").count() == 0
        ):  # Nothing to mark yet
            self.status = "NeedsGrading"
            if np.isnan(self.test.passing_score):
                return None, True, not self.passed
            numerically_passed = False
            pass_changed = False
            return self.score, numerically_passed, pass_changed
        numerically_passed = bool(  # deal with rouinding errors by checking with isclose as well as >=
            self.score >= self.test.passing_score or np.isclose(self.test.passing_score, self.score)
        )
        if orig:
            pass_changed = numerically_passed ^ orig.passed
        else:
            pass_changed = None
        self.status = "Graded"
        return self.score, numerically_passed, pass_changed

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        """Correct the passed flag if score is equal to or greater than test.passing_score."""
        if self.pk is not None:  # Get the old version from db
            orig = Test_Score.objects.get(pk=self.pk)
        else:  # New entry, no original to compare
            orig = None
            super().save(force_insert, force_update, using, update_fields)
            force_insert = False
        score, passed, send_signal = self.check_passed(orig)  # Have we passed now?
        task_logger.debug(f"Saving Test_Score {self.test.name} {score=} {passed=} {send_signal=}")

        self.passed = passed
        super().save(force_insert, force_update, using, update_fields)  # Save to ensure pk is set

        if self.test.category:  # Update the summary score if we have a category
            try:
                enrollment = ModuleEnrollment.objects.get(student=self.user, module=self.test.module)
                ss, _ = SummaryScore.objects.get_or_create(
                    enrollment=enrollment, category=self.test.category, student=self.user
                )
                ss.save()
            except ModuleEnrollment.DoesNotExist:  # Student de-registered from module!
                self.delete()
                return

        self.user.update_vitals = bool(send_signal)

    def __str__(self):
        """Give us a more friendly string version."""
        return f"{self.test.name} : {self.user.display_name} {'passed' if self.passed else 'not passed'}"


class Test_Attempt(models.Model):
    """Represents one attempt to do a Test by a Student."""

    attempt_id = models.CharField(max_length=255, unique=True)
    test_entry = models.ForeignKey(Test_Score, on_delete=models.CASCADE, related_name="attempts")
    status = models.CharField(choices=ATTEMPT_STATUS.items(), blank=True, null=True, max_length=40)
    text = models.TextField(blank=True, null=True)
    score = models.FloatField(null=True, blank=True)
    created = models.DateTimeField(blank=True, null=True)
    attempted = models.DateTimeField(blank=True, null=True)
    modified = models.DateTimeField(blank=True, null=True)
    override = models.BooleanField(default=False)

    def __str__(self):
        """Make simple string representation."""
        return f"{self.attempt_id} - for {self.test_entry}"


@patch_model(Account, prep=property)
def passed_tests(self):
    """Return the set of vitals passed by the current user, but not counting this that haven't started yet."""
    return Test.homework.filter(results__passed=True, results__user=self).exclude(status="Not Started")


@patch_model(Account, prep=property)
def failed_tests(self):
    """Return the set of vitals passed by the current user."""
    return Test.homework.filter(results__passed=False, results__user=self, status__in=["Finished", "Overdue"]).exclude(
        results__score=None
    )


@patch_model(Account, prep=property)
def untested_tests(self):
    """Return the set of vitals passed by the current user."""
    return Test.homework.exclude(results__user=self).exclude(status__in=["Released", "Not Started"])


@patch_model(Account, prep=property)
def passed_labs(self):
    """Return the set of vitals passed by the current user."""
    return Test.labs.filter(results__passed=True, results__user=self).exclude(status="Not Started")


@patch_model(Account, prep=property)
def failed_labs(self):
    """Return the set of vitals passed by the current user."""
    return Test.labs.filter(results__passed=False, results__user=self, status__in=["Finished", "Overdue"]).exclude(
        results__score=None
    )


@patch_model(Account, prep=property)
def untested_labs(self):
    """Return the set of vitals passed by the current user."""
    return Test.labs.exclude(results__user=self).exclude(status__in=["Released", "Not Started"])


@patch_model(Account, prep=property)
def passed_coding(self):
    """Return the set of vitals passed by the current user."""
    return Test.code_tasks.filter(results__passed=True, results__user=self).exclude(status="Not Started")


@patch_model(Account, prep=property)
def failed_coding(self):
    """Return the set of vitals passed by the current user."""
    return Test.code_tasks.filter(
        results__passed=False, results__user=self, status__in=["Finished", "Overdue"]
    ).exclude(results__score=None)


@patch_model(Account, prep=property)
def untested_coding(self):
    """Return the set of vitals passed by the current user."""
    return Test.code_tasks.exclude(results__user=self).exclude(status__in=["Released", "Not Started"])


@patch_model(Account)
def category_score(self, category):
    """Calculate the test summary from summary scores.

    Args:
        category (TestCategory, str):
            Category to get summary scores for (match single category if not str, otherwise match text).

    Returns:
        (float):
            credit weighted average of the summary scores for the categories with the matching names.
    """
    if isinstance(category, TestCategory):
        summaries = self.summary_scores.filter(category=category)
    else:
        summaries = self.summary_scores.filter(category__text=category)
    summary = np.array(summaries.values_list("module__credits", "score"))
    if summary.size == 0:  # No results must be a zero score
        return 0.0
    summary = summary.astype(float)
    return float(np.nansum(np.nanprod(summary, axis=1)) / np.nansum(summary[:, 0]))


@patch_model(Account, prep=property)
def tests_score(self):
    """Calculate the test summary from summary scores."""
    return getattr(self, "category_score")("Homework")


@patch_model(Account, prep=property)
def labs_score(self):
    """Calculate the test summary from summary scores."""
    return getattr(self, "category_score")("Lab Experiment")


@patch_model(Account, prep=property)
def coding_score(self):
    """Calculate the test summary from summary scores."""
    return getattr(self, "category_score")("Code Tasks")
