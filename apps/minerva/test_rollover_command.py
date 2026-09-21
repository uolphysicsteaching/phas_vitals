"""Tests for the academic-year rollover management command."""

# Python imports
import json
from datetime import date, datetime
from io import StringIO
from zoneinfo import ZoneInfo

# Django imports
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command

# external imports
import pytest
from accounts.models import Account, Cohort, TermDate, Year
from minerva.models import (
    Module,
    ModuleEnrollment,
    SummaryScore,
    Test as MinervaTest,
    Test_Attempt as MinervaTestAttempt,
    Test_Score as MinervaTestScore,
    TestCategory as MinervaTestCategory,
)
from tutorial.models import Attendance, Session
from vitals.models import VITAL, VITAL_Result


@pytest.fixture
def rollover_data(db, sample_status_code, sample_user, tmp_path):
    """Create locked and unlocked data spanning two academic years."""
    old_cohort = Cohort.objects.create(name="202425")
    new_cohort = Cohort.objects.create(name="202526")
    TermDate.objects.bulk_create(
        [
            TermDate(cohort=old_cohort, week=1, start=date(2024, 9, 30)),
            TermDate(cohort=old_cohort, week=14, start=date(2025, 1, 27)),
            TermDate(cohort=old_cohort, week=24, start=date(2025, 4, 21)),
            TermDate(cohort=new_cohort, week=1, start=date(2025, 9, 29)),
            TermDate(cohort=new_cohort, week=14, start=date(2026, 1, 26)),
            TermDate(cohort=new_cohort, week=24, start=date(2026, 4, 13)),
        ]
    )
    unlocked_module = Module.objects.create(
        uuid="unlocked-module",
        code="PHAS1111",
        name="Unlocked module",
        year=old_cohort,
        exam_code=1,
    )
    locked_user = type(sample_user).objects.create(
        username="locked-user",
        number=654321,
        email="locked@example.com",
        programme=sample_user.programme,
        year=sample_user.year,
    )
    unlocked_enrolment = ModuleEnrollment.objects.create(
        module=unlocked_module,
        student=sample_user,
        status=sample_status_code,
    )
    locked_enrolment = ModuleEnrollment.objects.create(
        module=unlocked_module,
        student=locked_user,
        status=sample_status_code,
        locked=True,
    )
    unlocked_category = MinervaTestCategory.objects.create(
        module=unlocked_module,
        category_id="unlocked",
        text="Unlocked category",
    )
    locked_category = MinervaTestCategory.objects.create(
        module=unlocked_module,
        category_id="locked",
        text="Locked category",
    )
    unlocked_summary = SummaryScore.objects.create(
        enrollment=unlocked_enrolment,
        category=unlocked_category,
        module=unlocked_module,
        student=sample_user,
    )
    locked_summary = SummaryScore.objects.create(
        enrollment=locked_enrolment,
        category=locked_category,
        module=unlocked_module,
        student=locked_user,
    )

    london = ZoneInfo("Europe/London")
    unlocked_test = MinervaTest.objects.create(
        module=unlocked_module,
        test_id="unlocked-test",
        name="Unlocked test",
        locked=True,
        release_date=datetime(2024, 10, 1, 9, 30, tzinfo=london),
        recommended_date=datetime(2025, 2, 3, 11, 15, tzinfo=london),
        grading_due=datetime(2025, 4, 22, 16, 45, tzinfo=london),
    )
    current_date = datetime(2025, 10, 7, 10, 0, tzinfo=london)
    locked_test = MinervaTest.objects.create(
        module=unlocked_module,
        test_id="locked-test",
        name="Locked test",
        release_date=current_date,
        recommended_date=current_date,
        grading_due=current_date,
    )
    unlocked_score, locked_score = MinervaTestScore._base_manager.bulk_create(
        [
            MinervaTestScore(user=sample_user, test=unlocked_test, passed=True),
            MinervaTestScore(user=locked_user, test=locked_test, passed=True),
        ]
    )
    unlocked_attempt, locked_attempt = MinervaTestAttempt._base_manager.bulk_create(
        [
            MinervaTestAttempt(attempt_id="unlocked-attempt", test_entry=unlocked_score, score=75),
            MinervaTestAttempt(attempt_id="locked-attempt", test_entry=locked_score, score=80),
        ]
    )
    unlocked_vital = VITAL.objects.create(name="Unlocked VITAL", module=unlocked_module)
    locked_vital = VITAL.objects.create(name="Locked VITAL", module=unlocked_module)
    unlocked_vital_result = VITAL_Result._base_manager.create(
        vital=unlocked_vital,
        user=sample_user,
        passed=True,
        locked=True,
    )
    locked_vital_result = VITAL_Result._base_manager.create(
        vital=locked_vital,
        user=locked_user,
        passed=True,
        locked=False,
    )
    session = Session.objects.create(
        name="Wk 1",
        semester=1,
        week=1,
        cohort=old_cohort,
        start=date(2024, 9, 30),
        end=date(2024, 10, 4),
    )
    attendance = Attendance.objects.create(student=sample_user, session=session, score=2)

    return {
        "backup_path": tmp_path / "rollover.json",
        "unlocked": (
            unlocked_enrolment,
            unlocked_summary,
            unlocked_score,
            unlocked_attempt,
            unlocked_vital_result,
        ),
        "locked": (locked_enrolment, locked_summary, locked_score, locked_attempt, locked_vital_result),
        "attendance": attendance,
        "unlocked_test": unlocked_test,
        "locked_test": locked_test,
        "current_date": current_date,
    }


@pytest.mark.django_db
class TestRolloverAcademicYearCommand:
    """Exercise safety checks, backups, deletions, and date mappings."""

    def test_term_date_find_uses_london_date_at_bst_split_point(self, db):
        """Interpret a UTC timestamp as its Europe/London teaching date."""
        cohort = Cohort.objects.create(name="202526")
        TermDate.objects.create(cohort=cohort, week=14, start=date(2026, 1, 26))
        split_point = TermDate.objects.create(cohort=cohort, week=23, start=date(2026, 4, 27))
        stored_value = datetime(2026, 4, 26, 23, 0, tzinfo=ZoneInfo("UTC"))

        result = TermDate.find(stored_value)

        assert result.pk == split_point.pk
        assert result.week == 23
        assert result.day == 0
        assert result.date == date(2026, 4, 27)
        assert result.time == datetime(2026, 4, 27, tzinfo=ZoneInfo("Europe/London")).time()

    def test_requires_a_numeric_student_cohort(self, monkeypatch, tmp_path):
        """Ignore special named cohorts when selecting the latest academic year."""
        Cohort.objects.create(name="non-student")
        prompted = False

        def record_prompt(_prompt):
            nonlocal prompted
            prompted = True
            return "yes"

        monkeypatch.setattr("builtins.input", record_prompt)
        with pytest.raises(CommandError, match="No numeric student cohorts exist"):
            call_command("rollover_academic_year", backup_path=tmp_path / "backup.json")

        assert prompted is False
        assert not (tmp_path / "backup.json").exists()

    def test_dry_run_reports_changes_without_prompting_or_writing(self, monkeypatch, rollover_data):
        """Leave all data untouched when the dry-run option is supplied."""
        prompted = False

        def record_prompt(_prompt):
            nonlocal prompted
            prompted = True
            return "yes"

        monkeypatch.setattr("builtins.input", record_prompt)
        stdout = StringIO()

        call_command(
            "rollover_academic_year",
            dry_run=True,
            backup_path=rollover_data["backup_path"],
            stdout=stdout,
        )

        assert prompted is False
        assert all(type(record)._base_manager.filter(pk=record.pk).exists() for record in rollover_data["unlocked"])
        rollover_data["unlocked_test"].refresh_from_db()
        assert rollover_data["unlocked_test"].release_date != datetime(
            2025, 9, 30, 9, 30, tzinfo=ZoneInfo("Europe/London")
        )
        assert not rollover_data["backup_path"].exists()
        assert "Dry run complete; no changes were made." in stdout.getvalue()

    def test_requires_term_dates_for_latest_cohort(self, monkeypatch, tmp_path):
        """Abort before prompting when the latest cohort has no term dates."""
        Cohort.objects.create(name="non-student")
        Cohort.objects.create(name="202627")
        prompted = False

        def record_prompt(_prompt):
            nonlocal prompted
            prompted = True
            return "yes"

        monkeypatch.setattr("builtins.input", record_prompt)
        with pytest.raises(CommandError, match=r"No term dates exist for the latest cohort \(2026/27\)"):
            call_command("rollover_academic_year", backup_path=tmp_path / "backup.json")

        assert prompted is False
        assert not (tmp_path / "backup.json").exists()

    def test_non_exact_confirmation_cancels(self, monkeypatch, rollover_data):
        """Accept only the exact lower-case confirmation and otherwise make no changes."""
        monkeypatch.setattr("builtins.input", lambda _prompt: "Yes")

        call_command("rollover_academic_year", backup_path=rollover_data["backup_path"])

        assert all(type(record)._base_manager.filter(pk=record.pk).exists() for record in rollover_data["unlocked"])
        assert not rollover_data["backup_path"].exists()

    def test_missing_next_student_year_aborts_before_prompt_or_deletion(self, monkeypatch, rollover_data):
        """Abort safely when an active student's next year cannot be resolved."""
        student_group = Group.objects.create(name="Student")
        student = rollover_data["unlocked"][0].student
        student.groups.add(student_group)
        prompted = False

        def record_prompt(_prompt):
            nonlocal prompted
            prompted = True
            return "yes"

        monkeypatch.setattr("builtins.input", record_prompt)
        with pytest.raises(CommandError, match="Cannot uniquely resolve year level 2"):
            call_command("rollover_academic_year", backup_path=rollover_data["backup_path"])

        assert prompted is False
        assert all(type(record)._base_manager.filter(pk=record.pk).exists() for record in rollover_data["unlocked"])
        assert not rollover_data["backup_path"].exists()

    def test_rollover_backs_up_deletions_and_preserves_locked_data(self, monkeypatch, rollover_data):
        """Delete only unlocked-enrolment data and independently remap old dates."""
        student_group = Group.objects.create(name="Student")
        second_year = Year.objects.create(name="Second Year", status="UG", level=2)
        third_year = Year.objects.create(name="Third Year", status="UG", level=3)
        masters_year = Year.objects.create(name="Masters", status="PGT", level=5)
        advancing_student = rollover_data["unlocked"][0].student
        advancing_student.year = second_year
        advancing_student.save(update_fields=["year"])
        advancing_student.groups.add(student_group)
        masters_student = Account.objects.create(
            username="masters-student",
            number=654323,
            year=third_year,
        )
        masters_student.groups.add(student_group)
        graduating_student = Account.objects.create(
            username="graduating-student",
            number=654322,
            year=masters_year,
        )
        graduating_student.groups.add(student_group)
        monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
        stdout = StringIO()

        call_command(
            "rollover_academic_year",
            backup_path=rollover_data["backup_path"],
            stdout=stdout,
        )

        assert not any(
            type(record)._base_manager.filter(pk=record.pk).exists() for record in rollover_data["unlocked"]
        )
        assert all(type(record)._base_manager.filter(pk=record.pk).exists() for record in rollover_data["locked"])
        assert Attendance.objects.filter(pk=rollover_data["attendance"].pk).exists()
        assert Session.objects.filter(cohort__name="202526").count() == 22
        advancing_student.refresh_from_db()
        masters_student.refresh_from_db()
        graduating_student.refresh_from_db()
        assert advancing_student.year == third_year
        assert advancing_student.is_active is True
        assert masters_student.year == masters_year
        assert masters_student.is_active is True
        assert graduating_student.year == masters_year
        assert graduating_student.is_active is False

        fixture = json.loads(rollover_data["backup_path"].read_text(encoding="utf-8"))
        fixture_models = [item["model"] for item in fixture]
        assert fixture_models == [
            "minerva.moduleenrollment",
            "minerva.summaryscore",
            "minerva.test_score",
            "minerva.test_attempt",
            "vitals.vital_result",
            "accounts.account",
            "accounts.account",
            "accounts.account",
        ]
        output = stdout.getvalue()
        assert "Unlocked module enrolments: 1" in output
        assert "Tests with dates before the current academic year: 1" in output
        assert "release_date: 1" in output
        assert "recommended_date: 1" in output
        assert "grading_due: 1" in output
        assert "Dates using calendar-year fallback: 0" in output
        assert "Student accounts to advance: 2" in output
        assert "Student accounts to archive: 1" in output
        assert "Tutorial sessions for 2025/26: 22 created, 0 updated." in output

        rollover_data["unlocked_test"].refresh_from_db()
        assert rollover_data["unlocked_test"].release_date == datetime(
            2025, 9, 30, 9, 30, tzinfo=ZoneInfo("Europe/London")
        )
        assert rollover_data["unlocked_test"].recommended_date == datetime(
            2026, 2, 2, 11, 15, tzinfo=ZoneInfo("Europe/London")
        )
        assert rollover_data["unlocked_test"].grading_due == datetime(
            2026, 4, 14, 16, 45, tzinfo=ZoneInfo("Europe/London")
        )
        rollover_data["locked_test"].refresh_from_db()
        assert rollover_data["locked_test"].release_date == rollover_data["current_date"]

    def test_vacation_date_uses_calendar_year_fallback(self, monkeypatch, rollover_data):
        """Move a vacation date forward by one calendar year when it has no teaching-week mapping."""
        test = rollover_data["unlocked_test"]
        test.release_date = datetime(2025, 4, 14, 9, 30, tzinfo=ZoneInfo("Europe/London"))
        test.save(update_fields=["release_date"])
        monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
        stdout = StringIO()

        call_command(
            "rollover_academic_year",
            backup_path=rollover_data["backup_path"],
            stdout=stdout,
        )

        test.refresh_from_db()
        assert test.release_date == datetime(2026, 4, 14, 9, 30, tzinfo=ZoneInfo("Europe/London"))
        assert "Dates using calendar-year fallback: 1" in stdout.getvalue()

    def test_existing_backup_is_not_overwritten_or_removed(self, monkeypatch, rollover_data):
        """Refuse an existing backup target without damaging it or deleting data."""
        rollover_data["backup_path"].write_text("keep me", encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

        with pytest.raises(CommandError, match="Could not write backup fixture"):
            call_command("rollover_academic_year", backup_path=rollover_data["backup_path"])

        assert rollover_data["backup_path"].read_text(encoding="utf-8") == "keep me"
        assert all(type(record)._base_manager.filter(pk=record.pk).exists() for record in rollover_data["unlocked"])

    def test_date_update_failure_rolls_back_all_deletions(self, monkeypatch, rollover_data):
        """Keep all database records if persisting the remapped dates fails."""
        monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

        def fail_bulk_update(_objects, _fields, batch_size=None):
            raise RuntimeError("simulated update failure")

        monkeypatch.setattr(MinervaTest._base_manager, "bulk_update", fail_bulk_update)
        with pytest.raises(RuntimeError, match="simulated update failure"):
            call_command("rollover_academic_year", backup_path=rollover_data["backup_path"])

        assert rollover_data["backup_path"].exists()
        assert all(type(record)._base_manager.filter(pk=record.pk).exists() for record in rollover_data["unlocked"])
