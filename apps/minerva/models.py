# Python imports
"""Models for integration with minerva."""
# Python imports
import logging
import re
from datetime import timedelta
from os import path

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import DEFAULT_DB_ALIAS, models
from django.forms import ValidationError
from django.utils import timezone as tz

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

update_vitals = celery_app.signature("minerva.tasks.update_vitals")
update_tests_score = celery_app.signature("accounts.tasks.update_tests_score")
update_labs_score = celery_app.signature("accounts.tasks.update_labs_score")
update_code_score = celery_app.signature("accounts.tasks.update_coding_score")


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


def match_name(name):
    """Match the name to column naming patterns."""
    lab_pattern = re.compile(config.LAB_PATTERN)
    homework_pattern = re.compile(config.HOMEWORK_PATTERN)
    code_pattern = re.compile(config.CODE_PATTERN)
    for pattern in (homework_pattern, code_pattern, lab_pattern):
        if match := pattern.match(name):
            name = match.groupdict()["name"]
            break
    return name


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
    def json_updated(self):
        """Get the last modified timestamp for the course_json file."""
        client = json.get_blob_client(self.course_json)
        return client.get_blob_properties()["last_modified"]

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
        qs = self.student_enrollments.filter(student__number__in=data.keys()).order_by("student__number")
        # First check whether we need to add some new enrollments
        add = list(set(data.keys()) - set([x[0] for x in qs.values_list("student__number")]))
        if add:
            students = Account.objects.filter(number__in=add, is_staff=False)  # GFet the student Accounbts to add
            for student in students:
                self.student_enrollments.model.objects.get_or_create(student=student, module=self)
            qs = self.student_enrollments.filter(student__number__in=data.keys()).order_by("student__number")
        if qs.count() < len(data):  # See if there are still accounts in Minerva that we haven't enrolled here
            # These could be staff users for example.
            enrolled = [x[0] for x in qs.values_list("student__number")]
            for number in list(data.keys()):
                if number not in enrolled:
                    del data[number]
        # Do the actual update.
        updates = []
        for enrollment in qs.all():
            enrollment.user_id = data[enrollment.student.number]
            updates.append(enrollment)
        qs.bulk_update(updates, ["user_id"])

    def update_from_json(self):
        """Update the module from json data."""
        try:
            self.update_enrollments()
        except IOError:
            return
        try:
            for test in self.tests.all():
                test.attempts_from_dicts()
        except IOError:
            return None
        return True


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
        passed = self.student.vital_results.filter(vital__in=vitals, passed=True)
        return vitals.count() == passed.count()


class Test_Manager(models.Manager):
    """Manager class for Test objects to support natural keys."""

    key_pattern = re.compile(r"(?P<name>.*)\s\((?P<module__code>[^\)]*)\)")

    def __init__(self, *args, **kargs):
        """Record the type filter."""
        self.type = kargs.pop("type", None)
        super().__init__(*args, **kargs)

    def get_queryset(self):
        """Annotate the query set with additional information based on the time."""
        zerotime = timedelta(0)
        qs = super().get_queryset()
        if self.type:
            qs = qs.filter(type=self.type)
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
    homework = Test_Manager(type="homework")
    labs = Test_Manager(type="lab_exp")
    code_tasks = Test_Manager(type="code_task")

    # test_id is actually a composite of course_id and column_id
    test_id = models.CharField(max_length=255, primary_key=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="tests")
    # Mandatory fields
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=10, choices=TEST_TYPES, default=TEST_TYPES[0][0])
    score_possible = models.FloatField(default=100, verbose_name="Maximum possible score")
    passing_score = models.FloatField(default=80, verbose_name="Passing score")
    grading_due = models.DateTimeField(blank=True, null=True, verbose_name="Minerva Due Date")
    release_date = models.DateTimeField(blank=True, null=True, verbose_name="Test Available Date")
    recommended_date = models.DateTimeField(blank=True, null=True, verbose_name="Recomemnded Attempt Date")
    grading_attemptsAllowed = models.IntegerField(blank=True, null=True, verbose_name="Number of allowed attempts")
    students = models.ManyToManyField("accounts.Account", through="Test_Score", related_name="tests")
    ignore_zero = models.BooleanField(
        default=False, blank=True, null=True, verbose_name="Zoer grades are not attempts"
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
        return [x.json_file for x in self.columns.all()]

    def natural_key(self):
        """Return string representation a natural key."""
        return str(self)

    def save(
        self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None
    ):  #  pylint: disable=arguments-differ
        """Check whether we need to update test_score passing fields."""
        if self.pk and self.results.count() > 0:
            orig = Test.objects.get(pk=self.pk)
            update_results = orig.passing_score != self.passing_score
        else:
            update_results = False
        super().save(force_insert, force_update, using, update_fields)
        if update_results:  # Propagate change in pass mark to test scores
            for test_score in self.results.all():  # Update all test_scores for both passes and fails
                test_score.save()

    def attempts_from_dicts(self):
        """Create a test attempt from with a single, or list of dictionaries derived from a json file."""
        for column in self.columns.all():
            column.update_attempts()

    def add_attempt(self, student, mark, date=None):
        """Add a Test_Attempt, including Test_Score as necessary."""
        score, _ = self.results.get_or_create(user=student)
        if not score.score or score.score < mark:
            score.score = mark
        if date is None:
            date = tz.now()
        attempt_id = f"{self.test_id}_{student.number}_{date.strftime('%Y%m%d')}_{mark}"
        score.save()
        try:
            attempt = score.attempts.get(attempt_id=attempt_id)
        except ObjectDoesNotExist:
            attempt = Test_Attempt(attempt_id=attempt_id, score=mark, test_entry=score)
        attempt.score = mark
        attempt.attempted = date
        attempt.modified = tz.now()
        attempt.save()

    @property
    def stats(self):
        """Return a dictionary of numbers who have attempted or not and passed or not."""
        potential = self.module.student_enrollments.filter(student__is_active=True).distinct().count()
        passed = self.results.filter(user__is_active=True, passed=True).count()
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
    def create_or_update_from_json(cls, module):
        """Create Test objects based on matching column names from a module's columns JSON file."""
        json_data = module.columns_json
        if (json_data := json.get_blob_by_name(module.columns_json, False)) is None:
            raise IOError(f"No JSON file for {module}")
        data = {x["id"]: x for x in json_data}

        new_data = {}
        for _, dictionary in data.items():
            name = match_name(dictionary["name"])  # get the column name
            new_data[name] = new_data.get(name, []) + [dictionary]  # Can have more than one JSON file per test
        data_ids = set(new_data.keys())
        for k in list(data_ids):  # Run through the keys that match tests
            for dictionary in new_data[k]:  # Run through the JSON files for each test
                try:
                    test = cls.objects.get(module=module, name=k)
                except ObjectDoesNotExist:
                    test = cls(test_id=dictionary["id"], module=module, name=k)
                test.grading_attemptsAllowed = dictionary["grading"]["attemptsAllowed"]
                test.score_possible = dictionary["score"]["possible"]
                test.save()
                column, _ = GradebookColumn.objects.get_or_create(gradebook_id=dictionary["id"])
                column.name = dictionary["name"]
                column.test = test
                column.save()

    @classmethod
    def get_by_column_name(cls, name, module=None):
        """Pattern match the name to see if we can locate a matching Test."""
        name = match_name(name)
        search = {"name": name}
        if module:
            search["module"] = module
        try:
            return cls.objects.get(**search)
        except cls.DoesNotExist:
            return None


class GradebookColumn(models.Model):
    """A representation of a single column in Minerva Gradebook that links to a Test."""

    gradebook_id = models.CharField(max_length=255)
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="columns", blank=True, null=True)
    name = models.CharField(max_length=255, null=True)

    class Meta:
        ordering = ["test__module__code", "test__name"]

    def __str__(self):
        """Refer to a column."""
        return f"{self.name} ({self.gradebook_id})"

    @property
    def json_file(self):
        """Return the name of the JSON column file."""
        return self.test.module.key + f"_Grade_Columns_Attempt_{self.gradebook_id}.json"

    def natural_key(self):
        """Return string representation a natural key."""
        return str(self)

    def update_attempts(self):
        """Update the TestAttempts from this Gradebook column."""
        json_data = json.get_blob_by_name(self.json_file)
        if json_data is None:
            raise IOError(f"No json blob {self.attemps_json}")
        json_data = {x["userId"]: x for x in json_data}
        qs = self.test.module.student_enrollments.filter(user_id__in=set(json_data.keys())).prefetch_related("student")
        for enrollment in qs.all():
            data = json_data.get(enrollment.user_id, None)
            if self.test.ignore_zero and data.get("score", None) == 0:  # By pass zero scores if we're ignoring them
                continue
            if data is None:  # No data for this enrollment for some reason
                continue
            if (
                data.get("score", None) is not None and data["score"] > self.test.score_possible
            ):  # Looks like core>max score
                continue  # so bypass this attempt
            result, _ = Test_Score.objects.get_or_create(user=enrollment.student, test=self.test)
            attempt, _ = Test_Attempt.objects.get_or_create(
                test_entry=result, attempt_id=f'{self.test.test_id}+{data["id"]}'
            )
            attempt.score = data.get("score", None)
            attempt.status = data.get("status", "NeedsGrading" if attempt.score is None else "Completed")
            attempt.created = pytz.utc.localize(data["created"])
            attempt.attempted = pytz.utc.localize(data["attemptDate"])
            attempt.modified = pytz.utc.localize(data["modified"])
            attempt.save()

    @classmethod
    def create_or_update_from_json(cls, module):
        """Use a modules' columns json data to create GradeScope column entities."""
        json_data = module.columns_json
        if (json_data := json.get_blob_by_name(module.columns_json, False)) is None:
            raise IOError(f"No JSON file for {module}")
        for column_data in json_data:
            column, _ = cls.objects.get_or_create(gradebook_id=column_data["id"], name=column_data["name"])
            if column.test is None:
                column.test = Test.get_by_column_name(column.name, module)  # Attempt to assign column to a Terst
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
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="results")
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
        mapping = {
            "Ok": "You passed:",  # PAssed
            "Overdue": "You can still pass:",  # Past the recomemneded time
            "Missing": "You can still pass:",  # No attempt at overdue test
            "Finished": "You would have passed:",  # Overdue passing
            "Released": "You will pass:",  # Underway, not passed yet
            "Not Started": "This will let you pass",
            "Waiting for Mark": "This will let you pass",
        }
        return mapping.get(self.manual_standing, "")

    def check_passed(self, orig=None):
        """Check whether the user has passed the test."""
        if self.attempts.exclude(status="NeedsGrading").count() == 0:  # Nothing to mark yet
            self.status = "NeedsGrading"
            return None, False, False
        best_score = np.round(self.attempts.aggregate(models.Max("score", default=0)).get("score__max", 0.0), 2)
        numerically_passed = bool(best_score and (best_score >= self.test.passing_score))
        if orig:
            pass_changed = numerically_passed ^ orig.passed
        else:
            pass_changed = None
        self.status = "Graded"
        return best_score, numerically_passed, pass_changed

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        """Correct the passed flag if score is equal to or greater than test.passing_score."""
        if self.pk is not None:
            orig = Test_Score.objects.get(pk=self.pk)
        else:
            orig = None
            super().save(force_insert, force_update, using, update_fields)
            force_insert = False
        score, passed, send_signal = self.check_passed(orig)
        task_logger.debug(f"Saving Test_Score {self.test.name} {score=} {passed=} {send_signal=}")
        self.score = score
        self.passed = passed
        super().save(force_insert, force_update, using, update_fields)
        update_vitals.delay(self.pk)
        if self.test.type == "homework":
            update_tests_score.delay(self.user.pk)
        elif self.test.type == "lab_exp":
            update_labs_score.delay(self.user.pk)
        elif self.test.type == "code_task":
            update_code_score.delay(self.user.pk)

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

    def __str__(self):
        """Make simple string representation."""
        return f"{self.attempt_id} - for {self.test_entry}"

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        """Check whether saving this attempt changes the test passed or not."""
        if not self.attempt_id:
            self.attempt_id = f"{self.test_entry.test.name}:{self.test_entry.user.username}:{self.attempted}"
        trigger_check = self.pk is None or self.test_entry.score != self.score
        super().save(force_insert, force_update, using, update_fields)

        if trigger_check:  # Every new attempt causes a save to the test_entry
            self.test_entry.save()


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
