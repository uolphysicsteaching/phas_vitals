"""Model objects for the VITALs app."""

# Python imports
import re
from datetime import timedelta

# Django imports
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone as tz

# external imports
import numpy as np
from accounts.models import Account
from constance import config

# Create your models here.
from util.models import colour, patch_model


class VITAL_Test_Map(models.Model):
    """The object that provides the mapping between minerva.Tests and vitals.VITAL."""

    test = models.ForeignKey("minerva.Test", on_delete=models.CASCADE, related_name="vitals_mappings")
    vital = models.ForeignKey("VITAL", on_delete=models.CASCADE, related_name="tests_mappings")
    necessary = models.BooleanField(default=False)
    sufficient = models.BooleanField(default=True)


class VITAL_ResultManager(models.Manager):
    """Annotate results with vitals status fields."""

    def get_queryset(self):
        """Annoteate the queryset with date information."""
        qs = super().get_queryset()
        zerotime = timedelta(0)
        qs = (
            qs.annotate(
                vital_release=models.Min("vital__tests__release_date"),
                vital_start_date=models.Min("vital__tests__release_date"),
                vital_end_date=models.Max("vital__tests__recommended_date"),
            )
            .annotate(
                from_start=tz.now() - models.F("vital_start_date"), from_end=tz.now() - models.F("vital_end_date")
            )
            .annotate(
                vital_status=models.Case(
                    models.When(from_end__gte=zerotime, then=models.Value("Finished")),
                    models.When(from_start__gte=zerotime, then=models.Value("Started")),
                    default=models.Value("Not Started"),
                )
            )
        ).order_by("vital__module", "vital_start_date")
        return qs


class VITAL_Result(models.Model):
    """Provide a model for connecting a VITAL to a student."""

    objects = VITAL_ResultManager()
    # Field definitions
    vital = models.ForeignKey("VITAL", on_delete=models.CASCADE, related_name="student_results")
    user = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="vital_results")
    passed = models.BooleanField(default=False)
    date_passed = models.DateTimeField(blank=True, null=True, verbose_name="Date Achieved")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["vital", "user"], name="Singleton mapping student and vital")]

    @property
    def status(self):
        """Calculate the status of this result object."""
        if self.passed:
            return "Ok"
        return self.vital.manual_satus

    @property
    def bootstrap5_class(self):
        """Get a Bootstrap 5 status class."""
        mapping = {
            "Ok": "bg-success text-light",  # PAssed
            "Finished": "bg-danger text-light",  # Overdue passing
            "Started": "bg-warning text-dark",  # Underway, not passed yet
            "Not Started": "text-dark",  # In the future, no worries yet
        }
        return mapping.get(self.status, "")

    @property
    def icon(self):
        """Get a suitable bootstrap5 icon class given our standing."""
        mapping = {
            "Ok": "bi bi-check",  # PAssed
            "Finished": "bi bi-x",  # Overdue passing
            "Started": "bi bi-x",  # Underway, not passed yet
        }
        return mapping.get(self.status, "")

    @property
    def tests_text(self):
        """Get text for advise about tests."""
        if self.vital.tests_mappings.count() == 0:
            mapping = {
                "Ok": "Requirements to be confirmed.",  # PAssed
                "Finished": "Requirements to be confirmed.",  # Overdue passing
                "Started": "Requirements to be confirmed.",  # Underway, not passed yet
                "Not Started": "Requirements to be confirmed.",  # In the future, no worries yet
            }
        elif self.vital.tests_mappings.count() == 1:
            mapping = {
                "Ok": "You passed:",  # PAssed
                "Finished": "You need to pass:",  # Overdue passing
                "Started": "Pass:",  # Underway, not passed yet
                "Not Started": "You will need to pass:",  # In the future, no worries yet
            }
        else:
            mapping = {
                "Ok": "You passed at least one of:",  # PAssed
                "Finished": "You need to pass at least one of:",  # Overdue passing
                "Started": "Pass one of these:",  # Underway, not passed yet
                "Not Started": "You will need to pass one of:",  # In the future, no worries yet
            }
        return mapping.get(self.status, "")


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
        zerotime = timedelta(0)
        qs = (
            qs.annotate(
                release=models.Min("tests__release_date"),
                start_date=models.Min("tests__release_date"),
                end_date=models.Max("tests__recommended_date"),
            )
            .annotate(from_start=tz.now() - models.F("start_date"), from_end=tz.now() - models.F("end_date"))
            .annotate(
                status=models.Case(
                    models.When(from_end__gte=zerotime, then=models.Value("Finished")),
                    models.When(from_start__gte=zerotime, then=models.Value("Started")),
                    default=models.Value("Not Started"),
                )
            )
        ).order_by("module", "start_date")
        return qs


class VITAL(models.Model):
    """A Verifiable Indicator of Threshold Ability and Learning."""

    objects = VITAL_Manager()
    # Fields
    name = models.CharField(max_length=255, blank=True, null=True)
    VITAL_ID = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    module = models.ForeignKey("minerva.Module", on_delete=models.CASCADE, related_name="VITALS")
    tests = models.ManyToManyField("minerva.Test", related_name="VITALS", through=VITAL_Test_Map)
    students = models.ManyToManyField("accounts.Account", through=VITAL_Result, related_name="VITALS")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name", "module"], name="Singleton VITAL name per module")]
        ordering = ["module__code", "VITAL_ID"]

    def natural_key(self):
        """Set natural key of a VITAL to be the string representation."""
        return str(self)

    @property
    def manual_satus(self):
        """Calculate the same as the annotation, but in python code."""
        zerotime = timedelta(0)
        data = self.tests.aggregate(
            release=models.Min("release_date"),
            start=models.Min("release_date"),
            end=models.Max("recommended_date"),
        )
        if data["start"] is None:
            return "Not Started"
        from_start = tz.now() - data.get("start", tz.now())
        if data["end"] is None:
            return "Not Started"
        from_end = tz.now() - data["end"]
        if from_end >= zerotime:
            return "Finished"
        if from_start >= zerotime:
            return "Started"
        return "Not Started"

    @property
    def bootstrap5_class(self):
        """Return a suitable background class for the urrent VITAL status."""
        mapping = {
            "Started": "bg-primary text-light",
            "Finished": "bg-secondary text-light",
            "Not Started": "bg-light test-dark",
        }
        return mapping.get(self.manual_satus, "")

    @property
    def url(self):
        """Return a url for the detail page for this vital."""
        return f"/vitals/detail/{self.pk}/"

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
        return f"{self.VITAL_ID}:{self.name} ({self.module.code}"


@patch_model(Account, prep=property)
def passed_vitals(self):
    """Return the set of vitals passed by the current user."""
    return VITAL.objects.filter(student_results__passed=True, student_results__user=self).exclude(status="Not Started")


@patch_model(Account, prep=property)
def failed_vitals(self):
    """Return the set of vitals passed by the current user."""
    return VITAL.objects.filter(student_results__passed=False, student_results__user=self).exclude(
        status="Not Started"
    )


@patch_model(Account, prep=property)
def untested_vitals(self):
    """Return the set of vitals passed by the current user."""
    return VITAL.objects.exclude(student_results__user=self).exclude(status="Not Started")


@patch_model(Account, prep=property)
def activity_label(self) -> str:
    """Monkey patched property for attendance ranking to a string."""
    translation = {
        "Exclellent": (90.0, 100.0),
        "Good": (60.0, 90.0),
        "Could be better": (40.0, 60.0),
        "Must Improve": (20.0, 40.0),
        "Unsatisfactory": (0, 20.0),
    }

    score = self.activity_score
    if not isinstance(score, (float, int)):
        return "No Data"
    for name, (low, high) in translation.items():
        if low <= score <= high:
            return name
    return "Unknown"


@patch_model(Account, prep=property)
def activity_colour(self) -> str:
    """Monkeypatch a routine to convert engagement scaore into a hex colour."""
    return colour(self.activity_score)
