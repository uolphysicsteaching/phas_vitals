# Python imports
import re

# Django imports
from django.core.exceptions import ObjectDoesNotExist
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


class VITAL_Manager(models.Manager):
    """Model Manager for VITALs to support natural keys."""

    key_pattern = re.compile(r"(?P<name>.*)\s\((?P<module__code>[^\)]*)\)")

    def get_by_natural_key(self, name):
        """Use ythe string representation as a natural key."""
        if match := self.key_pattern.match(name):
            return self.get(**match.groupdict())
        raise ObjectDoesNotExist(f"No VITAL {name}")

    def get_queryset(self):
        """Annoteate the queryset with date information."""
        qs = super().get_queryset()
        qs = qs.annotate(
            release=models.Min("tests__release_date"),
            start_date=models.Min("tests__recommended_date"),
            end_date=models.Max("tests__recommended_date"),
        )
        return qs


class VITAL(models.Model):
    """A Verifiable Indicator of Threshold Ability and Learning."""

    objects = VITAL_Manager()
    # Fields
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    module = models.ForeignKey("minerva.Module", on_delete=models.CASCADE, related_name="VITALS")
    tests = models.ManyToManyField("minerva.Test", related_name="VITALS", through=VITAL_Test_Map)
    students = models.ManyToManyField("accounts.Account", through=VITAL_Result, related_name="VITALS")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name", "module"], name="Singleton VITAL name per module")]

    def natural_key(self):
        """Set natural key of a VITAL to be the string representation."""
        return str(self)

    def passed(self, user, passed=True, date_passed=None):
        """Record the user as having passed this vital."""
        if not date_passed:
            date_passed = tz.now()
        result, _ = VITAL_Result.objects.get_or_create(vital=self, user=user)
        result.passed = passed
        if passed:
            result.date_passed = date_passed
        result.save()

    def check_vital(self, user):
        """Check whether a VITAL has been passed by a user."""
        # Check if any sufficient tests passed
        sufficient = self.tests_mappings.filter(sufficient=True)
        if user.test_results.filter(test__vitals_mappings__in=sufficient, passed=True).count() > 0:
            return self.passed(user)
        # Check all necessary tests are passed.
        necessary = self.tests_mappings.filter(necessary=True).distinct()
        if (
            necessary.count() > 0
            and user.test_results.filter(test__vitals_mappings_in=necessary, passed=True).distinct().count()
            == necessary.count()
        ):
            return self.passed(user)
        return self.passed(user, False)

    def __str__(self):
        """Use name and code as a string representation."""
        return f"{self.name} ({self.module.code}"
