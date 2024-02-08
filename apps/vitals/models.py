# Django imports
from django.db import models
from django.utils import timezone as tz

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
    passed = models.BooleanField(default=False)
    date_passed = models.DateTimeField(blank=True, null=True, verbose_name="Date Achieved")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["vital", "user"], name="Singleton mapping student and vital")]


class VITAL(models.Model):

    """A Verifiable Indicator of Threshold Ability and Learning."""

    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    module = models.ForeignKey("minerva.Module", on_delete=models.CASCADE, related_name="VITALS")
    tests = models.ManyToManyField("minerva.Test", related_name="VITALS", through=VITAL_Test_Map)
    students = models.ManyToManyField("accounts.Account", through=VITAL_Result, related_name="VITALS")

    def passed(self, user=None):
        """Record the user as having passed this vital."""
        result, new = VITAL_Result.objects.get_or_create(vital=self, user=user)
        result.passed = True
        result.date_passed = tz.now()
        result.save()
        
    def __str__(self):
        return f"{self.name} ({self.module.courseId}"
