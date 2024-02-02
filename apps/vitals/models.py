# Django imports
from django.db import models

# Create your models here.


class VITAL_Test_Map(models.Model):

    """The object that provides the mapping between minerva.Tests and vitals.VITAL."""

    test = models.ForeignKey("minerva.Test", on_delete=models.CASCADE, related_name="vitals_mappings")
    vital = models.ForeignKey("VITAL", on_delete=models.CASCADE, related_name="tests_mappings")
    necessary = models.BooleanField(default=False)
    sufficient = models.BooleanField(default=True)


class VITAL_Result(models.Model):

    """Provide a model for connecting a VITAL to a student."""

    vital = models.ForeignKey("VITAL", on_delete=models.CASCADE, related_name="student_results")
    user = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="vital_results")
    date_passed = models.DateTimeField(blank=True, null=True, verbose_name="Date Achieved")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["vital", "user"], name="Singleton mapping student and vital")]


class VITAL(models.Model):

    """A Verifiable Indicator of Threshold Ability and Learning."""

    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    module = models.ForeignKey("minerva.Module", on_delete=models.CASCADE, related_name="VITALS")
    tests = models.ManyToManyField("minerva.Test", related_name="VITALS", through=VITAL_Test_Map)
    students = models.ManyToManyField("accounts.Account", through=VITAL_Result,related_name="VITALS")
