"""Model objects for the VITALs app."""

# Python imports
import re
from datetime import timedelta
from itertools import chain

# Django imports
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone as tz
from django.utils.html import format_html

# external imports
import pandas as pd
from accounts.models import Account

# Create your models here.
from util.models import patch_model


def test_qs_to_html(queryset):
    """Produce an html list from a queryset."""
    if queryset.count() == 0:
        return ""
    ret = "<ul>\n"
    for test in queryset.all():
        ret += f"""<li><a class="vital_link" href="{test.url}">
            {test.name} ({test.module.code})</a></li>\n"""
    ret += "</ul>\n"
    return format_html(ret)


class VITAL_Test_Map(models.Model):
    """The object that provides the mapping between minerva.Tests and vitals.VITAL."""

    PASS_OPTIONS = [("pass", "Pass the test"), ("attempt", "Attempt the test")]

    test = models.ForeignKey("minerva.Test", on_delete=models.CASCADE, related_name="vitals_mappings")
    vital = models.ForeignKey("VITAL", on_delete=models.CASCADE, related_name="tests_mappings")
    necessary = models.BooleanField(default=False)
    sufficient = models.BooleanField(default=True)
    condition = models.CharField(max_length=10, choices=PASS_OPTIONS, default="pass")
    required_fractrion = models.FloatField(default=1.0)


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
            return {
                "Ok": "Requirements to be confirmed.",  # PAssed
                "Finished": "Requirements to be confirmed.",  # Overdue passing
                "Started": "Requirements to be confirmed.",  # Underway, not passed yet
                "Not Started": "Requirements to be confirmed.",  # In the future, no worries yet
            }.get(self.status, "")

        sufficient, sufficient_txt = self.vital.sufficient_pass_tests
        necessary, necessary_txt = self.vital.neccessary_attempt_tests
        ret = ""
        match self.status:
            case "Ok":  # passed
                if sufficient.count() >= 1:
                    ret += f"You passed {sufficient_txt}:\n{test_qs_to_html(sufficient)}"
                if necessary.count() >= 1:
                    ret += f"You attempted {necessary_txt}:\n{test_qs_to_html(necessary)}"
            case "Finished":
                if sufficient.count() >= 1:
                    ret += f"You still need to pass {sufficient_txt}:\n{test_qs_to_html(sufficient)}"
                if necessary.count() >= 1:
                    ret += f"You still need to attempt {necessary_txt}:\n{test_qs_to_html(necessary)}"
            case "Started":
                if sufficient.count() >= 1:
                    ret += f"You need to pass {sufficient_txt}:\n{test_qs_to_html(sufficient)}"
                if necessary.count() >= 1:
                    ret += f"You need to attempt {necessary_txt}:\n{test_qs_to_html(necessary)}"
            case "Not Started":
                if sufficient.count() >= 1:
                    ret += f"You will need to pass {sufficient_txt}:\n{test_qs_to_html(sufficient)}"
                if necessary.count() >= 1:
                    ret += f"You will need to attempt {necessary_txt}:\n{test_qs_to_html(necessary)}"
            case _:
                pass
        return format_html(ret)


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
    module = models.ForeignKey(
        "minerva.Module", on_delete=models.CASCADE, related_name="VITALS", blank=True, null=True
    )
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

    @property
    def stats(self):
        """Return a dictionary of numbers who have attempted or not and passed or not."""
        potential = self.module.student_enrollments.filter(student__is_active=True).distinct().count()
        passed = self.student_results.filter(user__is_active=True, passed=True).count()
        failed = self.student_results.filter(user__is_active=True, passed=False).count()
        ret = {
            "Passed": passed,
            "Failed": failed,
            "Not Attempted": potential - passed - failed,
        }
        return {k if v > 0 else "": v for k, v in ret.items()}

    @property
    def stats_legend(self):
        """Return a dictionary of items to use for the legend of a stats plot."""
        return {"Passed": "green", "Failed": "red", "Not Attempted": "black", "": "white"}

    @property
    def sufficient_pass_tests(self):
        """Return a queryset of the tests that are sufficient to pass this VITAL."""
        qs = self.tests.model.objects.filter(
            vitals_mappings__in=self.tests_mappings.filter(condition="pass", sufficient=True)
        ).distinct()
        if qs.count() == 1:
            return qs, ""
        return qs, "at least one of"

    @property
    def neccessary_attempt_tests(self):
        """Return a queryset and string label of number of necessary tests to attempt."""
        mappings = self.tests_mappings.filter(condition="attempt", necessary=True).distinct()
        number = mappings.aggregate(number=models.Sum("required_fractrion"))["number"]
        if number == mappings.count():
            output = "all of"
        else:
            number = round(number) if number else ""
            output = f"{number} of"
        return self.tests.model.objects.filter(vitals_mappings__in=mappings).distinct(), output

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
        necessary = self.tests_mappings.filter(necessary=True, condition="pass").distinct()
        if (
            necessary.count() > 0
            and user.test_results.filter(test__vitals_mappings_in=necessary, passed=True).distinct().count()
            == necessary.count()
        ):
            return self.passed(user)
        necessary = self.tests_mappings.filter(necessary=True, condition="attempt").distinct()
        needed = necessary.aggregate(needed=models.Sum("required_fractrion"))["needed"]
        if (
            necessary.count() > 0
            and user.test_results.filter(test__vitals_mappings__in=necessary).distinct().count() >= needed
        ):
            return self.passed(user)
        return self.passed(user, False)

    def __str__(self):
        """Use name and code as a string representation."""
        return f"{self.VITAL_ID}:{self.name} ({getattr(self.module, 'code', 'unassigned')}"


@patch_model(Account, prep=property)
def applicable_vitals(self):
    """All VITALs that are associated with a module that I am enrolled on."""
    return VITAL.objects.filter(module__in=self.modules.all())


@patch_model(Account, prep=property)
def passed_vitals(self):
    """Return the set of vitals passed by the current user."""
    return VITAL.objects.filter(student_results__passed=True, student_results__user=self).exclude(status="Not Started")


@patch_model(Account, prep=property)
def failed_vitals(self):
    """Return the set of vitals that gave finished and not been passed."""
    return VITAL.objects.filter(student_results__passed=False, student_results__user=self, status="Finished")


@patch_model(Account, prep=property)
def untested_vitals(self):
    """Return the set of vitals that the student doesn't have a result and that have finished."""
    return VITAL.objects.exclude(student_results__user=self).filter(status="Finished")


@patch_model(Account, prep=property)
def forthcoming_vitals(self):
    """Return the set of vitals that the student doesn't have a result and that have finished."""
    return VITAL.objects.exclude(student_results__user=self).filter(status="Not Started")


@patch_model(Account, prep=property)
def required_tests(self):
    """Calculate the minimum required tests to pass all failed VITALs."""
    data = []

    for vital in self.applicable_vitals.exclude(pk__in=[x.pk for x in self.passed_vitals.all()]):
        row = {"VITAL": vital.VITAL_ID}
        for test in vital.tests.all():
            row[test.test_id] = 1
        data.append(row)
    if not len(data):
        return Vital.objects.first().test.model.objects.none()
    data = pd.DataFrame(data).transpose().fillna(0.0)
    data.columns = data.loc["VITAL"]
    data = data.drop("VITAL")
    tests = []
    while True:
        best_test = data.index[data.sum(axis=1).argmax()]
        if data.loc[best_test].sum() == 0:
            break

        tests.append(best_test)
        data.loc[:, data.loc[best_test] == 1.0] = 0.0

    tests = vital.tests.model.objects.filter(test_id__in=tests).distinct().order_by("type", "release_date")

    return tests
