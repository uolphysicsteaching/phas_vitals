"""Model objects for the VITALs app."""

# Python imports
import re
from collections import defaultdict
from datetime import timedelta

# Django imports
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone as tz
from django.utils.html import format_html

# external imports
import numpy as np
import pandas as pd
from accounts.models import Account
from minerva.models import SummaryScore

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

    test = models.ForeignKey("minerva.Test", on_delete=models.CASCADE, to_field="id", related_name="vitals_mappings")
    vital = models.ForeignKey("VITAL", on_delete=models.CASCADE, related_name="tests_mappings")
    necessary = models.BooleanField(default=False)
    sufficient = models.BooleanField(default=True)
    condition = models.CharField(max_length=10, choices=PASS_OPTIONS, default="pass")
    required_fractrion = models.FloatField(default=1.0)

    def __str__(self):
        """Provide a sensible string for logging etc."""
        return (
            f"Mapping: {dict(self.PASS_OPTIONS)[self.condition]} {self.test.name} to pass {self.vital.name} "
            + f"{'neccessary' if self.necessary else ''} {'sufficient' if self.sufficient else ''}"
        )


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

    def bulk_update(self, objs, fields, batch_size=None):
        """Override to use a plain queryset, avoiding FieldError from ordering by aggregates."""
        return super().get_queryset().bulk_update(objs, fields, batch_size=batch_size)


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

    def bulk_update(self, objs, fields, batch_size=None):
        """Override to use a plain queryset, avoiding FieldError from ordering by aggregates."""
        return super().get_queryset().bulk_update(objs, fields, batch_size=batch_size)


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
    tests = models.ManyToManyField(
        "minerva.Test", related_name="VITALS", through=VITAL_Test_Map, through_fields=("vital", "test")
    )
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
        """Record the user as having passed this vital.

        Returns:
            True if user is updated, else False.
        """
        if not date_passed:
            date_passed = tz.now()
        result, _ = VITAL_Result.objects.get_or_create(vital=self, user=user)
        if passed and not result.passed:  # Update the pass status and date.
            if date_passed is None:
                date_passed = tz.now()
            result.date_passed = date_passed
        if result.passed ^ passed:
            result.passed = passed
            result.save()
            return True
        return False

    def check_vital(self, user):
        """Check whether a VITAL has been passed by a user."""
        TOLERANCE = 0.001
        all_mappings = list(self.tests_mappings.all())

        # Determine which tests the user has passed or merely attempted for this VITAL.
        user_passed_test_ids = frozenset(
            user.test_results.filter(test__vitals_mappings__in=all_mappings, passed=True)
            .values_list("test_id", flat=True)
            .distinct()
        )
        user_attempted_test_ids = frozenset(
            user.test_results.filter(test__vitals_mappings__in=all_mappings)
            .values_list("test_id", flat=True)
            .distinct()
        )

        def is_met(mapping):
            """Return True if the user has satisfied this mapping's condition."""
            if mapping.condition == "pass":
                return mapping.test_id in user_passed_test_ids
            return mapping.test_id in user_attempted_test_ids

        # Step 1: Award the VITAL if any sufficient mapping is met.
        if any(m.sufficient and is_met(m) for m in all_mappings):
            return self.passed(user)

        # No test results at all for this VITAL — return without recording.
        if not user_attempted_test_ids:
            return False

        # Step 2: Block the award if any necessary mapping is not met.
        # The condition is that the number of necessary mappings positively met (including the case
        # where a necessary test has no result at all, which counts as not met) equals the total
        # number of necessary mappings.
        necessary_mappings = [m for m in all_mappings if m.necessary]
        if len(necessary_mappings) > 0 and sum(1 for m in necessary_mappings if is_met(m)) != len(necessary_mappings):
            return self.passed(user, False)

        # Step 3: Award if the sum of required_fractrion for all met conditions >= 1.0.
        met_sum = sum(m.required_fractrion for m in all_mappings if is_met(m))
        if met_sum >= 1.0 - TOLERANCE:
            return self.passed(user)

        return self.passed(user, False)

    def check_vital_for_queryset(self, users):
        """Check whether this VITAL has been passed for each user in a queryset.

        Applies the same logic as :meth:`check_vital` but batches all database queries across the
        full set of users so that only a small constant number of queries are issued regardless of
        how many users are supplied.

        Args:
            users (QuerySet):
                A queryset of :class:`accounts.models.Account` instances to check.

        Returns:
            (int):
                The number of :class:`VITAL_Result` records that were created or updated (i.e.
                whose ``passed`` status changed).

        Examples:
            >>> students = module.students.all()
            >>> updated = vital.check_vital_for_queryset(students)
            >>> print(f"{updated} record(s) changed.")
        """
        TOLERANCE = 0.001
        now = tz.now()
        all_mappings = list(self.tests_mappings.all())
        if not all_mappings:
            return 0

        user_ids = list(users.values_list("pk", flat=True))
        if not user_ids:
            return 0

        TestScore = apps.get_model("minerva", "Test_Score")

        # Fetch all relevant test results for all users in two bulk queries.
        passed_pairs = (
            TestScore.objects.filter(
                test__vitals_mappings__in=all_mappings,
                user_id__in=user_ids,
                passed=True,
            )
            .values_list("user_id", "test_id")
            .distinct()
        )
        attempted_pairs = (
            TestScore.objects.filter(
                test__vitals_mappings__in=all_mappings,
                user_id__in=user_ids,
            )
            .values_list("user_id", "test_id")
            .distinct()
        )

        # Build per-user sets of passed and attempted test IDs.
        passed_by_user = defaultdict(set)
        for uid, tid in passed_pairs:
            passed_by_user[uid].add(tid)

        attempted_by_user = defaultdict(set)
        for uid, tid in attempted_pairs:
            attempted_by_user[uid].add(tid)

        necessary_mappings = [m for m in all_mappings if m.necessary]

        # Determine desired pass/fail outcome per user.
        # Maps user_id -> bool. Users with no test results at all are absent (no record written).
        results_to_set = {}
        for user_id in user_ids:
            user_passed = passed_by_user[user_id]
            user_attempted = attempted_by_user[user_id]

            def is_met(mapping, _passed=user_passed, _attempted=user_attempted):
                """Return True if the user has satisfied this mapping's condition."""
                if mapping.condition == "pass":
                    return mapping.test_id in _passed
                return mapping.test_id in _attempted

            # Step 1: Award if any sufficient mapping is met.
            if any(m.sufficient and is_met(m) for m in all_mappings):
                results_to_set[user_id] = True
                continue

            # No test results at all for this VITAL – do not record.
            if not user_attempted:
                continue

            # Step 2: Block if any necessary mapping is not met.
            if necessary_mappings and sum(1 for m in necessary_mappings if is_met(m)) != len(necessary_mappings):
                results_to_set[user_id] = False
                continue

            # Step 3: Award if the sum of required_fractrion for met conditions >= 1.0.
            met_sum = sum(m.required_fractrion for m in all_mappings if is_met(m))
            results_to_set[user_id] = met_sum >= 1.0 - TOLERANCE

        if not results_to_set:
            return 0

        # Load existing VITAL_Result records for affected users in a single query.
        existing = {
            r.user_id: r
            for r in VITAL_Result.objects.filter(vital=self, user_id__in=results_to_set.keys())
        }

        to_create = []
        to_update = []
        for user_id, should_pass in results_to_set.items():
            if user_id in existing:
                result = existing[user_id]
                if result.passed ^ should_pass:
                    if should_pass:
                        result.date_passed = now
                    result.passed = should_pass
                    to_update.append(result)
            else:
                to_create.append(
                    VITAL_Result(
                        vital=self,
                        user_id=user_id,
                        passed=should_pass,
                        date_passed=now if should_pass else None,
                    )
                )

        if to_create:
            VITAL_Result.objects.bulk_create(to_create)
        if to_update:
            VITAL_Result.objects.bulk_update(to_update, ["passed", "date_passed"])

        return len(to_create) + len(to_update)

    def __str__(self):
        """Use name and code as a string representation."""
        return f"{self.VITAL_ID}:{self.name} ({getattr(self.module, 'code', 'unassigned')}"


@patch_model(SummaryScore)
def calculate_vitals(self):
    """Patch a function to create a summary score object for a VITALs."""
    try:
        all_vitals = VITAL.objects.filter(module__in=self.student.modules.all()).exclude(status="Not Started")
        in_progress = all_vitals.exclude(student_results__user=self.student).exclude(status="Finished").count()

        vitals = self.student.vital_results.filter(vital__module__level=self.student.year.level)
        passed = vitals.filter(passed=True).count()
        self.score = np.round((100.0 * passed + 50 * in_progress) / all_vitals.count())
    except (ValueError, ZeroDivisionError):
        self.score = np.nan
    data = {}
    colours = {}
    status = []
    for vital in all_vitals:
        if vr := self.student.vital_results.filter(vital=vital).first():
            status.append(vr.status)
        else:
            status.append(vital.status)
    status = np.array(status)
    for stat, (label, colour) in settings.VITALS_RESULTS_MAPPING.items():
        if count := status[status == stat].size:
            data[label] = count
            colours[label] = colour
    self.data["data"] = data
    self.data["colours"] = colours
    return self.score


@patch_model(Account, prep=property)
def vitals_score(self):
    """Get VITALs score from Summary Score."""
    summary = np.array(self.summary_scores.filter(category__text="VITALs").values_list("module__credits", "score"))
    return float(summary.prod(axis=1).sum() / summary[:, 0].sum())


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
            row[test.pk] = 1
        data.append(row)
    if not len(data):
        Test = apps.get_model("minerva", "Test")
        return Test.objects.none()
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

    tests = vital.tests.model.objects.filter(pk__in=tests).distinct().order_by("category__text", "release_date")

    return tests
