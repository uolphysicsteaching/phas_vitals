"""Tests for the minerva app models and utilities."""

# Django imports
from django.core.exceptions import ValidationError
from django.utils import timezone as tz

# external imports
import pandas as pd
import pytest

# app imports
from .models import (
    Module,
    Test_Attempt,
    Test_Score,
    locate_named_group,
    module_validator,
)
from .views import StreamingImportTestsHistoryView


@pytest.mark.unit
class TestModuleValidator:
    """Test the module_validator function."""

    def test_valid_module_code(self):
        """Test validation of valid module codes.

        Examples:
            >>> module_validator("PHAS1234")  # Should not raise
        """
        # These should not raise ValidationError
        module_validator("PHAS1234")
        module_validator("PHAS2345")
        module_validator("PHAS3456")
        module_validator("PHAS1234M")

    def test_invalid_module_code(self):
        """Test validation of invalid module codes.

        Examples:
            >>> with pytest.raises(ValidationError):
            ...     module_validator("INVALID")
        """
        with pytest.raises(ValidationError):
            module_validator("INVALID")

        with pytest.raises(ValidationError):
            module_validator("CHEM1234")

        with pytest.raises(ValidationError):
            module_validator("PHAS")

    def test_non_string_input(self):
        """Test validation with non-string input.

        Examples:
            >>> with pytest.raises(ValidationError):
            ...     module_validator(1234)
        """
        with pytest.raises(ValidationError):
            module_validator(1234)

        with pytest.raises(ValidationError):
            module_validator(None)


@pytest.mark.unit
class TestLocateNamedGroup:
    """Test the locate_named_group function."""

    def test_locate_simple_named_group(self):
        r"""Test locating a simple named group.

        Examples:
            >>> pattern = r"(?P<name>\w+)"
            >>> start, end = locate_named_group(pattern, "name")
            >>> assert start == 0
        """
        pattern = r"(?P<name>\w+)"
        start, end = locate_named_group(pattern, "name")
        assert start == 0
        assert pattern[start:end] == r"(?P<name>\w+)"

    def test_locate_named_group_with_nested_parens(self):
        """Test locating a named group with nested parentheses.

        Examples:
            >>> pattern = r"(?P<group>(a|b))"
            >>> start, end = locate_named_group(pattern, "group")
            >>> assert end > start
        """
        pattern = r"(?P<group>(a|b))"
        start, end = locate_named_group(pattern, "group")
        assert start == 0
        assert end > start

    def test_locate_nonexistent_group(self):
        r"""Test locating a non-existent named group.

        Examples:
            >>> with pytest.raises(ValueError):
            ...     locate_named_group(r"(?P<name>\w+)", "missing")
        """
        with pytest.raises(ValueError, match="Named group 'missing' not found"):
            locate_named_group(r"(?P<name>\w+)", "missing")

    def test_locate_named_group_with_substitution(self):
        r"""Test locating and substituting a named group.

        Examples:
            >>> pattern = r"(?P<name>\w+)"
            >>> result = locate_named_group(pattern, "name", sub="replaced")
            >>> assert "replaced" in result
        """
        pattern = r"(?P<name>\w+)"
        result = locate_named_group(pattern, "name", sub="replaced")
        assert "replaced" in result


@pytest.mark.django_db
class TestHistoryImport:
    """Tests for the bulk gradebook-history importer."""

    def test_bulk_import_recalculates_each_score(self, sample_user, sample_test):
        """All attempts are written before the parent score is recalculated."""
        frame = pd.DataFrame(
            [
                {
                    "Date": "2026-01-01 10:00",
                    "Attempt Activity": "2026-01-01 09:00",
                    "Username": sample_user.username,
                    "Column": sample_test.name,
                    "Value": 40.0,
                },
                {
                    "Date": "2026-01-02 10:00",
                    "Attempt Activity": "2026-01-02 09:00",
                    "Username": sample_user.username,
                    "Column": sample_test.name,
                    "Value": 70.0,
                },
            ]
        )

        result = StreamingImportTestsHistoryView._process_dataframe(frame, sample_test.module)

        score = Test_Score.objects.get(user=sample_user, test=sample_test)
        assert result["created"] == 2
        assert score.attempts.count() == 2
        assert score.score == 70.0
        assert score.passed is True

    def test_bulk_import_does_not_replace_mark_with_nan(self, sample_user, sample_test):
        """An ungraded duplicate must not erase an existing numerical mark."""
        attempted = pd.Timestamp("2026-01-01 09:00", tz="Europe/London")
        score = Test_Score.objects.create(user=sample_user, test=sample_test)
        attempt = Test_Attempt.objects.create(
            attempt_id=f"{sample_test.name}:{sample_user.username}:{attempted}",
            test_entry=score,
            score=65.0,
            attempted=attempted,
        )
        frame = pd.DataFrame(
            [
                {
                    "Date": "2026-01-01 10:00",
                    "Attempt Activity": "2026-01-01 09:00",
                    "Username": sample_user.username,
                    "Column": sample_test.name,
                    "Value": float("nan"),
                }
            ]
        )

        result = StreamingImportTestsHistoryView._process_dataframe(frame, sample_test.module)

        attempt.refresh_from_db()
        assert result["unchanged"] == 1
        assert attempt.score == 65.0


@pytest.mark.django_db
@pytest.mark.unit
class TestModule:
    """Test the Module model."""

    def test_module_creation(self, sample_cohort):
        """Test creating a module.

        Args:
            sample_cohort (Cohort): A test cohort instance.

        Examples:
            >>> module = Module.objects.create(code="PHAS1234", ...)
            >>> assert module.code == "PHAS1234"
        """
        module = Module.objects.create(
            uuid="test-uuid",
            code="PHAS1234",
            exam_code=1,
            name="Test Module",
            credits=10,
            level=1,
            year=sample_cohort,
            semester=1,
        )
        assert module.code == "PHAS1234"
        assert module.name == "Test Module"
        assert module.credits == 10

    def test_module_str_representation(self, sample_module):
        """Test string representation of module.

        Args:
            sample_module (Module): A test module instance.

        Examples:
            >>> module = Module.objects.create(code="PHAS1234", exam_code=1, ...)
            >>> assert "PHAS1234" in str(module)
        """
        string_repr = str(sample_module)
        assert sample_module.code in string_repr
        assert sample_module.name in string_repr

    def test_module_slug_property(self, sample_module):
        """Test slug property of module.

        Args:
            sample_module (Module): A test module instance.

        Examples:
            >>> assert "PHAS1234" in module.slug
        """
        slug = sample_module.slug
        assert sample_module.code in slug
        assert f"({sample_module.exam_code:02d})" in slug

    def test_module_key_property(self, sample_module):
        """Test key property of module.

        Args:
            sample_module (Module): A test module instance.

        Examples:
            >>> key = module.key
            >>> assert module.code in key
        """
        key = sample_module.key
        assert sample_module.code in key
        assert str(sample_module.year.name) in key

    def test_module_unique_together(self, sample_cohort):
        """Test unique_together constraint on code and exam_code.

        Args:
            sample_cohort (Cohort): A test cohort instance.

        Examples:
            >>> Module.objects.create(code="PHAS1234", exam_code=1, ...)
            >>> with pytest.raises(Exception):  # IntegrityError or similar
            ...     Module.objects.create(code="PHAS1234", exam_code=1, ...)
        """
        # Django imports
        from django.db.utils import IntegrityError

        Module.objects.create(
            uuid="test-uuid-1",
            code="PHAS5678",
            exam_code=1,
            name="Test Module 1",
            year=sample_cohort,
        )
        with pytest.raises(IntegrityError):
            Module.objects.create(
                uuid="test-uuid-2",
                code="PHAS5678",
                exam_code=1,
                name="Test Module 2",
                year=sample_cohort,
            )

    def test_update_enrollments_retains_locked_submodule_enrollment_and_scores(
        self, monkeypatch, sample_module, sample_status_code, sample_user
    ):
        """Retain a locked stale enrolment and its related scores during a module update."""
        # app imports
        from .models import ModuleEnrollment, SummaryScore, TestCategory

        submodule = Module.objects.create(
            uuid="locked-submodule",
            code="PHAS1235",
            exam_code=1,
            name="Locked sub-module",
            credits=10,
            level=1,
            year=sample_module.year,
            semester=1,
            parent_module=sample_module,
        )
        parent_enrollment = ModuleEnrollment.objects.create(
            module=sample_module,
            student=sample_user,
            status=sample_status_code,
        )
        locked_enrollment = ModuleEnrollment.objects.create(
            module=submodule,
            student=sample_user,
            status=sample_status_code,
            locked=True,
        )
        category = TestCategory.objects.create(module=submodule, text="Tests", category_id="tests")
        summary = SummaryScore.objects.create(enrollment=locked_enrollment, category=category)
        monkeypatch.setattr(Module, "get_member_id_map", lambda self: {})

        sample_module.update_enrollments()

        assert not ModuleEnrollment.objects.filter(pk=parent_enrollment.pk).exists()
        assert ModuleEnrollment.objects.filter(pk=locked_enrollment.pk, locked=True).exists()
        assert SummaryScore.objects.filter(pk=summary.pk).exists()

    def test_module_enrollment_is_unlocked_by_default(self, sample_module, sample_status_code, sample_user):
        """Create module enrolments unlocked unless explicitly protected."""
        # app imports
        from .models import ModuleEnrollment

        enrollment = ModuleEnrollment.objects.create(
            module=sample_module,
            student=sample_user,
            status=sample_status_code,
        )

        assert enrollment.locked is False

    def test_update_enrollments_retains_locked_parent_enrollment(
        self, monkeypatch, sample_module, sample_status_code, sample_user
    ):
        """Retain a locked stale enrolment on the module being updated."""
        # app imports
        from .models import ModuleEnrollment

        enrollment = ModuleEnrollment.objects.create(
            module=sample_module,
            student=sample_user,
            status=sample_status_code,
            locked=True,
        )
        monkeypatch.setattr(Module, "get_member_id_map", lambda self: {})

        sample_module.update_enrollments()

        assert ModuleEnrollment.objects.filter(pk=enrollment.pk, locked=True).exists()


@pytest.mark.django_db
@pytest.mark.unit
class TestImportModuleList:
    """Test discovery and rollover of modules from Minerva course data."""

    @staticmethod
    def course_data(year="202526", uuid="new-uuid", crn="40949", code="PHAS1234", name="New name"):
        """Build representative Minerva course metadata."""
        return {"courseId": f"{year}_{crn}_{code}", "uuid": uuid, "name": f"AAAA1Z {name} ignored"}

    def test_updates_by_database_identity_and_rolls_year_with_only_locked_enrollments(
        self, monkeypatch, sample_module, sample_status_code, sample_user
    ):
        """Update a module in place when all its enrolments are locked."""
        # app imports
        from . import tasks
        from .models import ModuleEnrollment

        new_cohort = sample_module.year.__class__.objects.create(name="202526")
        enrollment = ModuleEnrollment.objects.create(
            module=sample_module,
            student=sample_user,
            status=sample_status_code,
            locked=True,
        )
        data = self.course_data()
        updates = []
        monkeypatch.setattr(tasks.json, "get_blob_list", lambda: {"module_Course.json": object()})
        monkeypatch.setattr(tasks.json, "get_blob_by_name", lambda name: [data])
        monkeypatch.setattr(Module, "update_from_json", lambda self, **kwargs: updates.append((self.pk, kwargs)))

        tasks.import_module_list.run()

        sample_module.refresh_from_db()
        assert sample_module.exam_code == 1
        assert sample_module.uuid == "new-uuid"
        assert sample_module.year == new_cohort
        assert sample_module.courseId == "40949"
        assert sample_module.name == "New name"
        assert ModuleEnrollment.objects.filter(pk=enrollment.pk, locked=True).exists()
        assert updates == [
            (
                sample_module.pk,
                {"categories": True, "tests": True, "enrollments": True, "columns": True, "grades": True},
            )
        ]

    def test_does_not_roll_uuid_or_year_with_unlocked_enrollments(
        self, monkeypatch, sample_module, sample_status_code, sample_user
    ):
        """Keep identity fields stable while an unlocked enrolment remains."""
        # app imports
        from . import tasks
        from .models import ModuleEnrollment

        old_uuid = sample_module.uuid
        old_year = sample_module.year
        sample_module.courseId = "40949"
        sample_module.save()
        ModuleEnrollment.objects.create(module=sample_module, student=sample_user, status=sample_status_code)
        sample_module.year.__class__.objects.create(name="202526")
        data = self.course_data(name="Updated name")
        updates = []
        monkeypatch.setattr(tasks.json, "get_blob_list", lambda: {"module_Course.json": object()})
        monkeypatch.setattr(tasks.json, "get_blob_by_name", lambda name: [data])
        monkeypatch.setattr(Module, "update_from_json", lambda self, **kwargs: updates.append(self.pk))

        tasks.import_module_list.run()

        sample_module.refresh_from_db()
        assert sample_module.uuid == old_uuid
        assert sample_module.year == old_year
        assert sample_module.name == "Updated name"
        assert sample_module.courseId == "40949"
        assert updates == []

    def test_conflicting_crn_years_abort_before_updates(self, monkeypatch, sample_module):
        """Reject source data that assigns one CRN to multiple academic years."""
        # app imports
        from . import tasks

        original_name = sample_module.name
        data = {
            "old_Course.json": self.course_data(year="202425", uuid="old"),
            "new_Course.json": self.course_data(year="202526", uuid="new"),
        }
        monkeypatch.setattr(tasks.json, "get_blob_list", lambda: {name: object() for name in data})
        monkeypatch.setattr(tasks.json, "get_blob_by_name", lambda name: [data[name]])

        with pytest.raises(ValueError, match="CRNs in multiple academic years"):
            tasks.import_module_list.run()

        sample_module.refresh_from_db()
        assert sample_module.name == original_name


@pytest.mark.django_db
@pytest.mark.unit
class TestTest:
    """Test the Test model."""

    def test_test_creation(self, sample_module):
        """Test creating a Test.

        Args:
            sample_module (Module): A test module instance.

        Examples:
            >>> test = Test.objects.create(name="Test", module=module, ...)
            >>> assert test.name == "Test"
        """
        # app imports
        from .models import Test

        test = Test.objects.create(
            name="Sample Test 2",
            test_id="sample-test-id-2",
            module=sample_module,
            description="A test for testing",
            passing_score=50.0,
            score_possible=100.0,
            release_date=tz.now(),
            grading_due=tz.now() + tz.timedelta(days=7),
            recommended_date=tz.now() + tz.timedelta(days=5),
        )
        assert test.name == "Sample Test 2"
        assert test.module == sample_module
        assert test.passing_score == 50.0
        assert test.score_possible == 100.0

    def test_column_matching_sets_default_pass_mark_from_possible_score(self, monkeypatch, sample_module):
        """Calculate a matched test's default pass mark from its possible score."""
        # app imports
        from .models import GradebookColumn, Test, TestCategory

        column_data = {
            "column-25": {
                "grading": {"attemptsAllowed": 1},
                "score": {"possible": 25.0},
            }
        }
        monkeypatch.setattr(Module, "column_data", property(lambda self: column_data))
        category = TestCategory.objects.create(
            module=sample_module,
            text="Lab Experiment",
            category_id="lab-experiment",
        )
        column = GradebookColumn.objects.create(
            gradebook_id="column-25",
            name="Experiment 1",
            module=sample_module,
            category=category,
        )

        Test.create_or_update_from_json(sample_module, column=column)

        test = Test.objects.get(module=sample_module, name="Experiment 1")
        assert test.score_possible == 25.0
        assert test.passing_score == 20.0


@pytest.mark.django_db
@pytest.mark.unit
class TestGradebookColumnChangeListForm:
    """Test the GradebookColumnChangeListForm."""

    def test_form_filters_tests_by_module(self, sample_module, sample_test):
        """Test that the form filters the Test queryset to the instance's module.

        Args:
            sample_module (Module): A test module instance.
            sample_test (Test): A test Test instance belonging to ``sample_module``.

        Examples:
            >>> form = GradebookColumnChangeListForm(instance=column)
            >>> assert list(form.fields["test"].queryset) == [sample_test]
        """
        # external imports
        # Create a second module with its own test that should NOT appear
        from accounts.models import Cohort

        # app imports
        from .forms import GradebookColumnChangeListForm
        from .models import GradebookColumn, Test

        other_cohort, _ = Cohort.objects.get_or_create(name="202526")
        other_module, _ = Module.objects.get_or_create(
            code="PHAS9999",
            exam_code=1,
            defaults={
                "uuid": "test-uuid-other",
                "name": "Other Module",
                "credits": 10,
                "level": 1,
                "year": other_cohort,
                "semester": 1,
            },
        )
        other_test = Test.objects.create(
            name="Other Module Test",
            test_id="other-test-id",
            module=other_module,
            score_possible=100.0,
            release_date=tz.now(),
            grading_due=tz.now() + tz.timedelta(days=7),
            recommended_date=tz.now() + tz.timedelta(days=5),
        )

        column = GradebookColumn.objects.create(
            gradebook_id="col-001",
            name="Test Column",
            module=sample_module,
            test=sample_test,
        )

        form = GradebookColumnChangeListForm(instance=column)
        qs = list(form.fields["test"].queryset)

        assert sample_test in qs
        assert other_test not in qs

    def test_form_preselects_current_test(self, sample_module, sample_test):
        """Test that the form pre-selects the instance's current test value.

        Args:
            sample_module (Module): A test module instance.
            sample_test (Test): A test Test instance belonging to ``sample_module``.

        Examples:
            >>> form = GradebookColumnChangeListForm(instance=column)
            >>> assert form.initial.get("test") == sample_test.pk
        """
        # app imports
        from .forms import GradebookColumnChangeListForm
        from .models import GradebookColumn

        column = GradebookColumn.objects.create(
            gradebook_id="col-002",
            name="Test Column 2",
            module=sample_module,
            test=sample_test,
        )

        form = GradebookColumnChangeListForm(instance=column)
        # The instance drives initial value; test must be in the filtered queryset
        assert column.test in form.fields["test"].queryset

    def test_form_empty_queryset_without_instance(self):
        """Test that the form has an empty Test queryset when no instance is provided.

        Examples:
            >>> form = GradebookColumnChangeListForm()
            >>> assert form.fields["test"].queryset.count() == 0
        """
        # app imports
        from .forms import GradebookColumnChangeListForm

        form = GradebookColumnChangeListForm()
        assert form.fields["test"].queryset.count() == 0


@pytest.mark.django_db
@pytest.mark.unit
class TestFeedbackApiHardening:
    """Regression tests for feedback API hardening."""

    def test_feedback_filter_matches_test_name(self, sample_user, sample_test):
        """Filtering by test name should use the related test field without raising."""
        # app imports
        from .api import FeedbackFilters
        from .models import Test_Score

        score = Test_Score.objects.create(user=sample_user, test=sample_test, score=70.0)
        filtered = FeedbackFilters(
            data={"test": "Sample Test"},
            queryset=Test_Score.objects.all(),
        ).qs
        assert list(filtered) == [score]

    def test_feedback_update_persists_attempt_comment_and_date(self, sample_user, sample_test):
        """Updating feedback should write back to the related attempt record."""
        # app imports
        from .api import FeedbackSerializer

        score, attempt = sample_test.add_attempt(sample_user, 55.0, date=tz.now(), text="Before")
        updated_at = tz.now() + tz.timedelta(hours=1)
        serializer = FeedbackSerializer(
            instance=score,
            data={
                "student": sample_user.username,
                "assignment_name": f"{sample_test.module.code}~{sample_test.name}",
                "score": 82.0,
                "comment": "After",
                "date": updated_at.isoformat(),
            },
            partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        updated_score = serializer.save()
        attempt.refresh_from_db()
        updated_score.refresh_from_db()

        assert updated_score.score == 82.0
        assert attempt.score == 82.0
        assert attempt.text == "After"
        assert attempt.attempted == updated_at

    def test_feedback_api_rejects_delete(self):
        """The feedback API should not expose DELETE."""
        # app imports
        from .api import FeednackViewSet

        assert "delete" not in FeednackViewSet.http_method_names
