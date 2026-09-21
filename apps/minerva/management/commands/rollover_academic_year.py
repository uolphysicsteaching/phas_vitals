"""Roll the retained academic data forwards to the latest cohort."""

# Python imports
from datetime import timedelta
from itertools import chain
from pathlib import Path

# Django imports
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

# external imports
from accounts.models import Account, Cohort, TermDate, Year
from dateutil.relativedelta import relativedelta
from minerva.models import (
    ModuleEnrollment,
    SummaryScore,
    Test,
    Test_Attempt,
    Test_Score,
)
from tutorial.models import Session
from vitals.models import VITAL_Result


class Command(BaseCommand):
    """Delete superseded student data and move old test dates into the latest cohort."""

    help = "Back up and roll academic data and student accounts into the latest cohort."
    date_fields = ("release_date", "recommended_date", "grading_due")
    student_levels = (0, 1, 2, 3, 5)

    def add_arguments(self, parser):
        """Add the dry-run flag and optional fixture output path.

        Args:
            parser (argparse.ArgumentParser):
                The command-line argument parser.

        Examples:
            ``manage.py rollover_academic_year --backup-path /safe/place/rollover.json``
        """
        parser.add_argument(
            "--backup-path",
            type=Path,
            help="Path for the JSON backup fixture (must not already exist).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the planned rollover without prompting, writing a backup, or changing the database.",
        )

    def handle(self, *args, **options):
        """Perform an explicitly confirmed academic-year rollover.

        Args:
            *args (tuple):
                Positional command arguments supplied by Django.

        Keyword Parameters:
            **options (dict):
                Parsed management-command options.

        Raises:
            CommandError:
                If term dates or date mappings are unavailable, or the backup cannot be written.

        Examples:
            ``manage.py rollover_academic_year``
        """
        cohort = self._latest_student_cohort()
        if cohort is None:
            raise CommandError("No numeric student cohorts exist; the academic-year rollover cannot proceed.")
        if not cohort.termdates.exists():
            raise CommandError(f"No term dates exist for the latest cohort ({cohort}).")

        cutoff = self._week_zero_start(cohort)
        deletion_querysets = self._deletion_querysets()
        shifted_dates, affected_test_count, field_counts, fallback_count = self._shifted_test_dates(cohort, cutoff)
        student_updates, students_advanced, students_archived, students_without_year = self._student_year_updates()
        student_accounts = Account._base_manager.filter(pk__in=[student.pk for student in student_updates])

        self.stdout.write(f"Latest cohort: {cohort}")
        self.stdout.write(f"Start of semester 1 week 0: {cutoff.isoformat()}")
        self.stdout.write("Records to delete:")
        for label, queryset in deletion_querysets:
            self.stdout.write(f"  {label}: {queryset.count()}")
        self.stdout.write(f"Tests with dates before the current academic year: {affected_test_count}")
        for field in self.date_fields:
            self.stdout.write(f"  {field}: {field_counts[field]}")
        self.stdout.write(f"Dates using calendar-year fallback: {fallback_count}")
        self.stdout.write(f"Student accounts to advance: {students_advanced}")
        self.stdout.write(f"Student accounts to archive: {students_archived}")
        self.stdout.write(f"Active student accounts without a year (unchanged): {students_without_year}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run complete; no changes were made."))
            return

        confirmation = input("Type yes to back up these records and perform the rollover: ")
        if confirmation != "yes":
            self.stdout.write(self.style.WARNING("Academic-year rollover cancelled; no changes were made."))
            return

        backup_path = options.get("backup_path") or self._default_backup_path()
        self._write_backup(backup_path, (*deletion_querysets, ("Student accounts", student_accounts)))

        with transaction.atomic():
            # Child rows are deliberately removed explicitly. Locks on them do not override an unlocked enrolment.
            deletion_map = dict(deletion_querysets)
            deletion_map["Test attempts"].delete()
            deletion_map["Test scores"].delete()
            deletion_map["VITAL results"].delete()
            deletion_map["Summary scores"].delete()
            deletion_map["Unlocked module enrolments"].delete()

            tests = list(Test._base_manager.filter(pk__in=shifted_dates))
            for test in tests:
                for field, value in shifted_dates[test.pk].items():
                    setattr(test, field, value)
            if tests:
                Test._base_manager.bulk_update(tests, self.date_fields)
            if student_updates:
                Account._base_manager.bulk_update(student_updates, ("year", "is_active"))
            try:
                sessions_created, sessions_updated = Session.create_for_cohort(cohort)
            except ValueError as error:
                raise CommandError(f"Tutorial sessions cannot be created for the latest cohort: {error}") from error

        self.stdout.write(self.style.SUCCESS(f"Backup fixture written to {backup_path}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Tutorial sessions for {cohort}: {sessions_created} created, {sessions_updated} updated."
            )
        )
        self.stdout.write(self.style.SUCCESS("Academic-year rollover completed."))

    @staticmethod
    def _latest_student_cohort():
        """Return the latest cohort whose name is an all-digit student cohort code."""
        student_cohorts = (cohort for cohort in Cohort.objects.all() if cohort.name.isdigit())
        return max(student_cohorts, key=lambda cohort: int(cohort.name), default=None)

    def _week_zero_start(self, cohort):
        """Return the start of week zero for a cohort."""
        try:
            week_one = TermDate.reverse(cohort, 1, 0).datetime
        except (AttributeError, Cohort.DoesNotExist) as error:
            raise CommandError(f"Semester 1 cannot be mapped for the latest cohort ({cohort}).") from error
        return week_one - timedelta(weeks=1)

    def _deletion_querysets(self):
        """Build querysets for records owned by unlocked enrolments."""
        unlocked = ModuleEnrollment._base_manager.filter(locked=False)
        matching_test_enrolment = unlocked.filter(
            student_id=OuterRef("user_id"),
            module_id=OuterRef("test__module_id"),
        )
        test_scores = Test_Score._base_manager.filter(Exists(matching_test_enrolment))
        matching_vital_enrolment = unlocked.filter(
            student_id=OuterRef("user_id"),
            module_id=OuterRef("vital__module_id"),
        )
        vital_results = VITAL_Result._base_manager.filter(Exists(matching_vital_enrolment))
        return (
            ("Unlocked module enrolments", unlocked.order_by("pk")),
            ("Summary scores", SummaryScore._base_manager.filter(enrollment__in=unlocked).order_by("pk")),
            ("Test scores", test_scores.order_by("pk")),
            ("Test attempts", Test_Attempt._base_manager.filter(test_entry__in=test_scores).order_by("pk")),
            ("VITAL results", vital_results.order_by("pk")),
        )

    def _shifted_test_dates(self, cohort, cutoff):
        """Precompute and validate each old test-date mapping independently."""
        old_date_filter = Q()
        for field in self.date_fields:
            old_date_filter |= Q(**{f"{field}__lt": cutoff})

        shifted = {}
        field_counts = {field: 0 for field in self.date_fields}
        fallback_count = 0
        for test in Test._base_manager.filter(old_date_filter).order_by("pk"):
            test_dates = {}
            for field in self.date_fields:
                value = getattr(test, field)
                if value is None or value >= cutoff:
                    continue
                local_value = timezone.localtime(value) if timezone.is_aware(value) else value
                try:
                    old_term_date = TermDate.find(value)
                except ValueError:
                    test_dates[field] = local_value + relativedelta(years=1)
                    fallback_count += 1
                    field_counts[field] += 1
                    continue
                try:
                    new_term_date = TermDate.reverse(cohort, old_term_date.week, old_term_date.day)
                except (AttributeError, Cohort.DoesNotExist, ValueError) as error:
                    raise CommandError(f"Cannot map {field} for test {test.pk} ({test}): {value}.") from error
                new_term_date.time = local_value.time()
                test_dates[field] = new_term_date.datetime
                field_counts[field] += 1
            shifted[test.pk] = test_dates
        return shifted, len(shifted), field_counts, fallback_count

    def _student_year_updates(self):
        """Prepare year advancement and archiving for active student accounts."""
        students = list(
            Account._base_manager.filter(groups__name="Student", is_active=True).select_related("year").distinct()
        )
        years_by_level = {}
        for year in Year.objects.exclude(level=None).order_by("pk"):
            years_by_level.setdefault(year.level, []).append(year)

        updates = []
        advanced = 0
        archived = 0
        without_year = 0
        for student in students:
            if student.year is None or student.year.level is None:
                without_year += 1
                continue
            if student.year.level >= 5:
                student.is_active = False
                archived += 1
            else:
                next_level = next(level for level in self.student_levels if level > student.year.level)
                candidates = years_by_level.get(next_level, [])
                same_status = [year for year in candidates if year.status == student.year.status]
                if len(same_status) == 1:
                    student.year = same_status[0]
                elif len(candidates) == 1:
                    student.year = candidates[0]
                else:
                    raise CommandError(
                        f"Cannot uniquely resolve year level {next_level} for student {student.username}."
                    )
                advanced += 1
            updates.append(student)
        return updates, advanced, archived, without_year

    def _default_backup_path(self):
        """Build a timestamped default backup path below MEDIA_ROOT."""
        timestamp = timezone.now().strftime("%Y%m%dT%H%M%S%f")
        return Path(settings.MEDIA_ROOT) / "backups" / f"academic-year-rollover-{timestamp}.json"

    def _write_backup(self, backup_path, deletion_querysets):
        """Write all records selected for deletion to a restorable JSON fixture."""
        backup_path = Path(backup_path).expanduser()
        created = False
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with backup_path.open("x", encoding="utf-8") as stream:
                created = True
                serializers.serialize(
                    "json",
                    chain.from_iterable(queryset.iterator() for _, queryset in deletion_querysets),
                    indent=2,
                    stream=stream,
                )
        except Exception as error:
            if created and backup_path.exists():
                backup_path.unlink()
            raise CommandError(f"Could not write backup fixture to {backup_path}: {error}") from error
