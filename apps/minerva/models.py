# Python imports
import re
from os import path
from pathlib import Path

# Django imports
from django.conf import settings
from django.db import models
from django.core.exceptions import ObjectDoesNotExist

from django.forms import ValidationError

# external imports
import numpy as np
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
    pattern = MOD_PATTERN
    if not isinstance(value, str) or not pattern.match(value):
        raise ValidationError("Module code must be PHYS module code")


class ModuleManager(models.Manager):
    def get_queryset(self):
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

    students = models.ManyToManyField("accounts.Account", related_name="modules", through="ModuleEnrollment")
    objects = ModuleManager()

    class Meta:
        ordering = ("code", "exam_code")
        unique_together = ("code", "exam_code")
        permissions = [
            ("can_excport", "Can Export Modules as cvs"),
            ("can_download", "Can Download completed modules"),
            ("can_list_all", "Can List all modules"),
        ]

    def __str__(self):
        return f"{self.code}({self.exam_code:02d}): {self.name}"

    @property
    def slug(self):
        return f"{self.code}({self.exam_code:02d})"

    @property
    def plotable(self):
        return not np.isnan(self.module_mean)

    @property
    def initials(self):
        if "-" in self.name:
            name = self.name.split("-")[0]
        else:
            name = self.name
        parts = [x for x in name.split(" ") if len(x) > 0 and x[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"]
        return "".join([x[0] for x in parts]).upper()

    @property
    def module_variance(self):
        if self.entries.all().count() == 0:
            return np.nan
        marks = self.entries.all().prefetch_related("student").order_by("student__number")
        variances = np.array([mark.variance for mark in marks])
        weights = np.ma.MaskedArray(
            [(1 / mark.student.score_std) if mark.student.score_std > 0 else 0.001 for mark in marks]
        ).astype(float)
        mask = np.logical_or(np.isnan(variances), np.isnan(weights))
        variances = variances[~mask]
        weights = weights[~mask]
        if len(weights) == 0:
            return np.nan
        return np.average(variances, weights=weights)

    @property
    def module_mean(self):
        """Calculate the mean mark for this module."""
        if self.entries.all().count() == 0:
            return np.nan
        scores = np.atleast_2d(np.array(self.entries.values_list("score")))[:, 0].astype(float)
        scores = scores[~np.isnan(scores)]
        if len(scores) == 0:
            return np.nan
        return np.mean(scores)

    @property
    def module_median(self):
        """Calculate the mean mark for this module."""
        if self.entries.all().count() == 0:
            return np.nan
        scores = np.atleast_2d(np.array(self.entries.values_list("score")))[:, 0].astype(float)
        scores = scores[~np.isnan(scores)]
        if len(scores) == 0:
            return np.nan
        return np.median(scores)

    @property
    def module_std(self):
        """Calculate the mean mark for this module."""
        if self.entries.all().count() == 0:
            return np.nan
        scores = np.atleast_2d(np.array(self.entries.values_list("score")))[:, 0].astype(float)
        scores = scores[~np.isnan(scores)]
        if len(scores) < 2:
            return np.nan
        return np.std(scores)

    @property
    def pass_mark(self):
        return 40.0 if self.level < 4 else 50.0

    @property
    def submitted(self):
        args = {"submitted": True}
        if config.RESITS_ONLY:
            args["status__resit"] = True
        return self.entries.filter(**args)

    @property
    def missing(self):
        args = {"submitted": False}
        if config.RESITS_ONLY:
            args["status__resit"] = True
        return self.entries.filter(**args)

    @property
    def most_recent_upload(self):
        """Get the most recent file from the upload directories."""
        mstats = sorted([(f.lstat().st_mtime, f) for f in self.upload_path.glob("*.xlsx")], reverse=True)
        if len(mstats) == 0:
            return None
        return mstats[0][1]

    @property
    def resit_upload_path(self):
        return self.upload_path.parent / "resit"

    @property
    def semester_upload_path(self):
        return self.upload_path.parent / f"S{self.semester}"

    def save(self, *args, **kargs):
        self.level = int(self.code[4])
        if self.credits == 0 and not "999" in self.code:
            # Try to guess a sensible default credit level.
            self.credits = 10 if self.level < 3 else 15
        super().save(*args, **kargs)

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


class ModuleEnrollment(models.Model):

    """Records students enrolled on modules."""

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="student_enrollments")
    student = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="module_enrollments")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["module", "student"], name="Singleton EWnrollment on a module")
        ]


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
        return str(self)


class Test_Score(models.Model):

    """The model that links a particular student to a particular test."""

    user = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="test_results")
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="results")
    status = models.CharField(choices=SCORE_STATUS.items(), max_length=50)
    text = models.TextField(blank=True, null=True)
    score = models.FloatField(null=True, blank=True)
    passed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["test", "user"], name="Singleton mapping student and test_score")
        ]

    def save(self, **kargs):
        """Correct the passed flag if score is equal to or greate than test.passing_score."""
        if self.pk:
            if self.test.grading_attemptsAllowed and self.test.grading_attemptsAllowed > 0:
                attempts = self.attempts.count() <= self.test.grading_attemptsAllowed
            else:
                attempts = True
            best_score = self.attempts.aggregate(models.Max("score", default=0)).get("score__max", None)
            self.score = self.score if self.score else best_score

            if self.score and self.test.passing_score:
                numerically_passed = self.score >= self.test.passing_score
            else:
                numerically_passed = False
        else:
            attempts = False
            numerically_passed = False
        send_signal = not self.passed and numerically_passed and attempts
        self.passed = self.passed or (numerically_passed and attempts)
        super().save(**kargs)
        if send_signal:
            test_passed.send(sender=self.__class__, test=self)

    def __str__(self):
        """Give us a more friendly string version."""
        return f"{self.test.name} : {self.user.display_name} {'passed' if self.passed else 'not passed'}"


class Test_Attempt(models.Model):

    """Represents one attempt to do a Test by a Student."""

    attempt_id = models.CharField(max_length=255, primary_key=True)
    test_entry = models.ForeignKey(Test_Score, on_delete=models.CASCADE, related_name="attempts")
    status = models.CharField(choices=ATTEMPT_STATUS.items(), blank=True, null=True, max_length=40)
    text = models.TextField(blank=True, null=True)
    score = models.FloatField(null=True, blank=True)
    created = models.DateTimeField(blank=True, null=True)
    attempted = models.DateTimeField(blank=True, null=True)
    modified = models.DateTimeField(blank=True, null=True)

    def save(self, **kargs):
        """Check whether saving this attempt changes the test passed or not."""
        trigger_check = self.pk is None or self.test_entry.score != self.score
        super().save(**kargs)

        if trigger_check:  # Every new attempt causes a save to the test_entry
            self.test_entry.save()
