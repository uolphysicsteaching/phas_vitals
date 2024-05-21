# Python imports
"""Models for integration with minerva."""
# Python imports
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
from accounts.models import Account
from constance import config
from util.models import patch_model
from util.spreadsheet import Spreadsheet

# app imports
from phas_vitals import celery_app

update_vitals = celery_app.signature("minerva.update_vitals")

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
MOD_PATTERN = re.compile(rf"{config.SUBJECT_PREFIX}[0123589][0-9]{{3}}M?")


def module_validator(value):
    """Validate module code patterns."""
    pattern = MOD_PATTERN
    if not isinstance(value, str) or not pattern.match(value):
        raise ValidationError(f"Module code must be {config.SUBJECT_PREFIX} module code")


class ModuleManager(models.Manager):
    """Add extra calculated attributes to the queryset."""

    def get_queryset(self):
        """Annoteate query set."""
        return super().get_queryset().annotate(enrollments=models.Count("students"))


class Module(models.Model):
    """Represents a single module marksheet."""

    uuid = models.CharField(max_length=32)
    courseId = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=11, null=False, blank=False, validators=[module_validator])
    alt_code = models.CharField(max_length=11, null=True, blank=True)  # For merged Modules
    credits = models.IntegerField(default=0)
    name = models.CharField(max_length=80)
    level = models.IntegerField(null=True, blank=True)
    semester = models.IntegerField(null=True, blank=True)
    exam_code = models.IntegerField(default=1, null=False, blank=False)
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


class ModuleEnrollment(models.Model):
    """Records students enrolled on modules."""

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="student_enrollments")
    student = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="module_enrollments")
    status = models.ForeignKey(StatusCode, on_delete=models.SET_DEFAULT, default="RE")

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
        """Setup the type filter."""
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

    TEST_TYPES = [("homework", "Homework"), ("lab_exp", "Lab Experiment")]

    objects = Test_Manager()
    homework = Test_Manager(type="homework")
    labs = Test_Manager(type="lab_exp")

    # test_id is actually a composite of course_id and column_id
    test_id = models.CharField(max_length=255, primary_key=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="tests")
    # Mandatory fields
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=10, choices=TEST_TYPES, default=TEST_TYPES[0][0])
    externalGrade = models.BooleanField(default=True, verbose_name="Grade from LTI")
    score_possible = models.FloatField(default=100, verbose_name="Maximum possible score")
    passing_score = models.FloatField(default=80, verbose_name="Maximum possible score")
    grading_due = models.DateTimeField(blank=True, null=True, verbose_name="Minerva Due Date")
    release_date = models.DateTimeField(blank=True, null=True, verbose_name="Test Available Date")
    recommended_date = models.DateTimeField(blank=True, null=True, verbose_name="Recomemnded Attempt Date")
    grading_attemptsAllowed = models.IntegerField(blank=True, null=True, verbose_name="Number of allowed attempts")
    students = models.ManyToManyField("accounts.Account", through="Test_Score", related_name="tests")

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
        from_release = tz.now() - self.release_date
        from_recommended = tz.now() - self.recommended_date
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

    def natural_key(self):
        """Return string representation a natural key."""
        return str(self)

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        """Check whether we need to update test_score passing fields."""
        if self.results.count() > 0:
            orig = Test.objects.get(pk=self.pk)
            update_results = orig.passing_score != self.passing_score
        else:
            update_results = False
        super().save(force_insert, force_update, using, update_fields)
        if update_results:  # Propagate change in pass mark to test scores
            for test_score in self.results.all():  # Update all test_scores for both passes and fails
                test_score.save()


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
                    models.When(passed=False, then=models.F("test_status")), default=models.Value("Ok")
                )
            )
        )

        return qs


class Test_Score(models.Model):
    """The model that links a particular student to a particular test."""

    objects = TestScoreManager()
    ### Fields ###########################################################
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
        }
        return mapping.get(self.manual_standing, "")

    @property
    def vitals_text(Self):
        """Get a Label for whether we pass VITALS or not."""
        mapping = {
            "Ok": "You passed:",  # PAssed
            "Overdue": "You can still pass:",  # Past the recomemneded time
            "Missing": "You can still pass:",  # No attempt at overdue test
            "Finished": "You would have passed:",  # Overdue passing
            "Released": "You will pass:",  # Underway, not passed yet
            "Not Started": "This will let you pass",
        }
        return mapping.get(Self.manual_standing, "")

    def check_passed(self, orig=None):
        """Check whether the user has passed the test."""
        best_score = self.attempts.aggregate(models.Max("score", default=0)).get("score__max", 0.0)
        numerically_passed = bool(best_score and (best_score >= self.test.passing_score))
        if orig:
            pass_changed = numerically_passed ^ orig.passed
        else:
            pass_changed = None
        return best_score, numerically_passed, pass_changed

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        """Correct the passed flag if score is equal to or greater than test.passing_score."""
        if self.pk is not None:
            orig = Test_Score.objects.get(pk=self.pk)
        else:
            orig = None
            super().save(force_insert, force_update, using, update_fields)
        score, passed, send_signal = self.check_passed(orig)
        self.score = score
        self.passed = passed
        super().save(force_insert, force_update, using, update_fields)
        if send_signal:
            update_vitals.delay_on_commit(self.pk)

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
        self.attempt_id = f"{self.test_entry.test.name}:{self.test_entry.user.username}:{self.attempted}"
        trigger_check = self.pk is None or self.test_entry.score != self.score
        super().save(force_insert, force_update, using, update_fields)

        if trigger_check:  # Every new attempt causes a save to the test_entry
            self.test_entry.save()


@patch_model(Account, prep=property)
def passed_tests(self):
    """Return the set of vitals passed by the current user."""
    return Test.objects.filter(results__passed=True, results__user=self).exclude(status="Not Started")


@patch_model(Account, prep=property)
def failed_tests(self):
    """Return the set of vitals passed by the current user."""
    return Test.objects.filter(results__passed=False, results__user=self).exclude(status="Not Started")


@patch_model(Account, prep=property)
def untested_tests(self):
    """Return the set of vitals passed by the current user."""
    return Test.objects.exclude(results__user=self).exclude(status="Not Started")
