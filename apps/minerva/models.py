# Python imports
import re
from os import path

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.forms import ValidationError

# external imports
from constance import config
from util.spreadsheet import Spreadsheet

# app imports
from .signals import test_passed

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
        """Has the user passed all the vitals on this module?"""
        vitals = self.module.VITALS.all()
        passed = self.student.vital_results.filter(vital__in=vitals, passed=True)
        return vitals.count() == passed.count()


class Test_Manager(models.Manager):
    """Manager class for Test objects to support natural keys."""

    key_pattern = re.compile(r"(?P<name>.*)\s\((?P<module__code>[^\)]*)\)")

    def get_by_natural_key(self, name):
        """Use ythe string representation as a natural key."""
        if match := self.key_pattern.match(name):
            return self.get(**match.groupdict())
        raise ObjectDoesNotExist(f"No VITAL {name}")


class Test(models.Model):
    """Represents a single Gradebook column."""

    objects = Test_Manager()
    # test_id is actually a composite of course_id and column_id
    test_id = models.CharField(max_length=255, primary_key=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="tests")
    # Mandatory fields
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    externalGrade = models.BooleanField(default=True, verbose_name="Grade from LTI")
    score_possible = models.FloatField(default=100, verbose_name="Maximum possible score")
    passing_score = models.FloatField(default=80, verbose_name="Maximum possible score")
    grading_due = models.DateTimeField(blank=True, null=True, verbose_name="Minerva Due Date")
    release_date = models.DateTimeField(blank=True, null=True, verbose_name="Test Available Date")
    recommended_date = models.DateTimeField(blank=True, null=True, verbose_name="Recomemnded Attempt Date")
    grading_attemptsAllowed = models.IntegerField(blank=True, null=True, verbose_name="Number of allowed attempts")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["module", "name"], name="Singleton name of a test per module")]

    def __str__(self):
        """Nicer name."""
        return f"{self.name} ({self.module.code})"

    def natural_key(self):
        """Return string representation a natural key."""
        return str(self)

    def save(self, **kargs):
        """Check whether we need to update test_score passing fields."""
        if self.results.count() > 0:
            orig = Test.objects.get(pk=self.pk)
            update_results = orig.passing_score != self.passing_score
        else:
            update_results = False
        super().save(**kargs)
        if update_results:  # Propagate change in pass mark to test scores
            for test_score in self.results.all():  # Update all test_scores for both passes and fails
                test_score.save()


class TestScoreManager(models.Manager):
    """Annotate with number of attempts."""

    def get_queryset(
        self,
    ):
        """Annoteate query set with number of attempts at test."""
        return super().get_queryset().annotate(attempt_count=models.Count("attempts"))


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

    def check_passed(self, orig=None):
        """Check whether the user has passed the test."""
        best_score = self.attempts.aggregate(models.Max("score", default=0)).get("score__max", 0.0)
        numerically_passed = bool(best_score and (best_score >= self.test.passing_score))
        if orig:
            pass_changed = numerically_passed ^ orig.passed
        else:
            pass_changed = None
        return best_score, numerically_passed, pass_changed

    def save(self, **kargs):
        """Correct the passed flag if score is equal to or greate than test.passing_score."""
        if self.pk is not None:
            orig = Test_Score.objects.get(pk=self.pk)
        else:
            orig = None
            super().save()
        score, passed, send_signal = self.check_passed(orig)
        self.score = score
        self.passed = passed
        super().save()
        if send_signal:
            test_passed.send(sender=self.__class__, test=self)

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
        """Simple string representation."""
        return f"{self.attempt_id} - for {self.test_entry}"

    def save(self, **kargs):
        """Check whether saving this attempt changes the test passed or not."""
        self.attempt_id = f"{self.test_entry.test.name}:{self.test_entry.user.username}:{self.attempted}"
        trigger_check = self.pk is None or self.test_entry.score != self.score
        super().save()

        if trigger_check:  # Every new attempt causes a save to the test_entry
            self.test_entry.save()
