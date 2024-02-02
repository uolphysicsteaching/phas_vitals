# Django imports
from django.db import models

# Create your models here.


ATTEMPT_STATUS = {
    "NotAttempted": "None of the students in a group has submitted an attempt",
    "InProgress": "Attempt activity has commenced, but has not been submitted for grading",
    "NeedsGrading": "Attempt has been submitted for grading, but has not been fully graded",
    "Completed": "A grade has been entered for the attempt",
    "InProgressAgain": "New student activity occurred after the grade was entered",
    "NeedsGradingAgain": "New Student activity needs grade ipdating",
}

SCORE_STATUS = {"Graded": "Score Graded", "NeedsGrading": "Not Marked Yet"}


class Module(models.Model):

    """Mdel object for a single Module (Leanr Ultra Course)."""

    id = models.CharField(max_length=255, primary_key=True)
    uuid = models.CharField(max_length=32)
    courseId = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    programmes = models.ManyToManyField("accounts.Programme", related_name="modules")


class Test(models.Model):

    """Represents a single Gradebook column."""

    # test_id is actually a composite of course_id and column_id
    test_id = models.CharField(max_length=255, primary_key=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="tests")
    # Mandatory fields
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    externalGrade = models.BooleanField(default=True, verbose_name="Grade from LTI")
    score_possible = models.IntegerField(default=100, verbose_name="Maximum possible score")
    grading_due = models.DateTimeField(blank=True, null=True, verbose_name="Minerva Due Date")
    release_date = models.DateTimeField(blank=True, null=True, verbose_name="Test Available Date")
    recommended_date = models.DateTimeField(blank=True, null=True, verbose_name="Recomemnded Attempt Date")
    grading_attemptsAllowed = models.IntegerField(blank=True, null=True, verbose_name="Number of allowed attempts")


class Test_Score(models.Model):

    """The model that links a particular student to a particular test."""

    user = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="test_results")
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="results")
    status = models.CharField(choices=SCORE_STATUS.items(), max_length=50)
    text = models.TextField(blank=True, null=True)
    score = models.FloatField(null=True, blank=True)


class Test_Attempt(models.Model):

    """Represents one attempt to do a Test by a Student."""

    attempt_id = models.CharField(max_length=255, primary_key=True)
    test_entry = models.ForeignKey(Test_Score, on_delete=models.CASCADE, related_name="attempts")
    status = models.CharField(choices=ATTEMPT_STATUS.items(), blank=True, null=True,max_length=40)
    text = models.TextField(blank=True, null=True)
    score = models.FloatField(null=True, blank=True)
    created = models.DateTimeField(blank=True, null=True)
    attempted = models.DateTimeField(blank=True, null=True)
    modified = models.DateTimeField(blank=True, null=True)
