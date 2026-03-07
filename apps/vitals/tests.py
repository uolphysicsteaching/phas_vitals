"""Tests for the vitals app models."""

# Django imports
from django.db.utils import IntegrityError
from django.utils import timezone as tz

# external imports
import pytest

# app imports
from .models import VITAL, VITAL_Result, VITAL_Test_Map


@pytest.mark.django_db
@pytest.mark.unit
class TestVITAL_Test_Map:
    """Test the VITAL_Test_Map model."""

    def test_vital_test_map_creation(self, sample_test, sample_vital):
        """Test creating a VITAL to Test mapping.

        Args:
            sample_test (Test): A test Test instance.
            sample_vital (VITAL): A test VITAL instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital)
            >>> assert mapping.test == test
        """
        mapping = VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, necessary=False, sufficient=True)
        assert mapping.test == sample_test
        assert mapping.vital == sample_vital
        assert mapping.necessary is False
        assert mapping.sufficient is True

    def test_vital_test_map_str_representation(self, sample_test, sample_vital):
        """Test string representation of VITAL_Test_Map.

        Args:
            sample_test (Test): A test Test instance.
            sample_vital (VITAL): A test VITAL instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital)
            >>> assert "pass" in str(mapping).lower()
        """
        mapping = VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, condition="pass")
        string_repr = str(mapping)
        assert sample_test.name in string_repr
        assert sample_vital.name in string_repr
        assert "pass" in string_repr.lower()

    def test_vital_test_map_default_values(self, sample_test, sample_vital):
        """Test default values for VITAL_Test_Map.

        Args:
            sample_test (Test): A test Test instance.
            sample_vital (VITAL): A test VITAL instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital)
            >>> assert mapping.sufficient is True
        """
        mapping = VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital)
        assert mapping.necessary is False
        assert mapping.sufficient is True
        assert mapping.condition == "pass"
        assert mapping.required_fractrion == 1.0


@pytest.mark.django_db
@pytest.mark.unit
class TestVITAL_Result:
    """Test the VITAL_Result model."""

    def test_vital_result_creation(self, sample_vital, sample_user):
        """Test creating a VITAL result.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.

        Examples:
            >>> result = VITAL_Result.objects.create(vital=vital, user=user)
            >>> assert result.vital == vital
        """
        result = VITAL_Result.objects.create(vital=sample_vital, user=sample_user, passed=False)
        assert result.vital == sample_vital
        assert result.user == sample_user
        assert result.passed is False

    def test_vital_result_passed(self, sample_vital, sample_user):
        """Test VITAL result with passed status.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.

        Examples:
            >>> result = VITAL_Result.objects.create(vital=vital, user=user, passed=True)
            >>> assert result.status == "Ok"
        """
        result = VITAL_Result.objects.create(vital=sample_vital, user=sample_user, passed=True, date_passed=tz.now())
        assert result.passed is True
        assert result.status == "Ok"

    def test_vital_result_unique_constraint(self, sample_vital, sample_user):
        """Test unique constraint on vital and user.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.

        Examples:
            >>> VITAL_Result.objects.create(vital=vital, user=user)
            >>> with pytest.raises(IntegrityError):
            ...     VITAL_Result.objects.create(vital=vital, user=user)
        """
        VITAL_Result.objects.create(vital=sample_vital, user=sample_user)
        with pytest.raises(IntegrityError):
            VITAL_Result.objects.create(vital=sample_vital, user=sample_user)

    def test_vital_result_bootstrap5_class(self, sample_vital, sample_user):
        """Test Bootstrap 5 class property.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.

        Examples:
            >>> result = VITAL_Result.objects.create(vital=vital, user=user, passed=True)
            >>> assert "success" in result.bootstrap5_class
        """
        result = VITAL_Result.objects.create(vital=sample_vital, user=sample_user, passed=True)
        assert "success" in result.bootstrap5_class

    def test_vital_result_icon(self, sample_vital, sample_user):
        """Test icon property.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.

        Examples:
            >>> result = VITAL_Result.objects.create(vital=vital, user=user, passed=True)
            >>> assert "check" in result.icon
        """
        result = VITAL_Result.objects.create(vital=sample_vital, user=sample_user, passed=True)
        assert "check" in result.icon


@pytest.mark.django_db
@pytest.mark.unit
class TestVITAL:
    """Test the VITAL model."""

    def test_vital_creation(self, sample_module):
        """Test creating a VITAL.

        Args:
            sample_module (Module): A test module instance.

        Examples:
            >>> vital = VITAL.objects.create(name="Test VITAL", module=module)
            >>> assert vital.name == "Test VITAL"
        """
        vital = VITAL.objects.create(name="Test VITAL", module=sample_module, description="Test description")
        assert vital.name == "Test VITAL"
        assert vital.module == sample_module

    def test_vital_with_id(self, sample_module):
        """Test VITAL with VITAL_ID attribute.

        Args:
            sample_module (Module): A test module instance.

        Examples:
            >>> vital = VITAL.objects.create(name="Test VITAL", module=module, VITAL_ID="V001")
            >>> assert vital.VITAL_ID == "V001"
        """
        vital = VITAL.objects.create(name="ID VITAL", module=sample_module, VITAL_ID="V001")
        assert vital.VITAL_ID == "V001"


@pytest.mark.django_db
@pytest.mark.unit
class TestVITALAdminActions:
    """Test the underlying model operations used by the VITALAdmin action methods."""

    def test_delete_vital_results_removes_results(self, sample_vital, sample_user):
        """Test that deleting VITAL_Result objects via queryset filter works correctly.

        This validates the model operation performed by the delete_vital_results admin action.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.

        Examples:
            >>> VITAL_Result.objects.create(vital=vital, user=user)
            >>> VITAL_Result.objects.filter(vital__in=[vital]).delete()
            >>> assert VITAL_Result.objects.filter(vital=vital).count() == 0
        """
        VITAL_Result.objects.create(vital=sample_vital, user=sample_user)
        assert VITAL_Result.objects.filter(vital=sample_vital).count() == 1

        queryset = VITAL.objects.filter(pk=sample_vital.pk)
        VITAL_Result.objects.filter(vital__in=queryset).delete()

        assert VITAL_Result.objects.filter(vital=sample_vital).count() == 0

    def test_delete_vital_results_only_affects_selected_vitals(self, sample_vital, sample_user, sample_module):
        """Test that the delete operation only removes results for VITALs in the queryset.

        This validates the selectivity of the model operation used by delete_vital_results.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_module (Module): A test module instance.

        Examples:
            >>> VITAL_Result.objects.create(vital=vital1, user=user)
            >>> VITAL_Result.objects.create(vital=vital2, user=user)
            >>> VITAL_Result.objects.filter(vital__in=[vital1]).delete()
            >>> assert VITAL_Result.objects.filter(vital=vital2).count() == 1
        """
        other_vital = VITAL.objects.create(name="Other VITAL", module=sample_module, VITAL_ID="V002")
        VITAL_Result.objects.create(vital=sample_vital, user=sample_user)
        VITAL_Result.objects.create(vital=other_vital, user=sample_user)

        queryset = VITAL.objects.filter(pk=sample_vital.pk)
        VITAL_Result.objects.filter(vital__in=queryset).delete()

        assert VITAL_Result.objects.filter(vital=sample_vital).count() == 0
        assert VITAL_Result.objects.filter(vital=other_vital).count() == 1

    def test_check_vital_creates_result_for_passing_student(
        self, sample_vital, sample_user, sample_test, sample_module
    ):
        """Test that check_vital creates a passing VITAL_Result when a student has passed a sufficient test.

        This validates the model operation performed by the create_vital_results admin action.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital, sufficient=True, condition="pass")
            >>> Test_Score.objects.create(test=test, user=user, passed=True)
            >>> vital.check_vital(user)
            >>> assert VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        # external imports
        from minerva.models import Test_Score

        # Enrol the user in the module
        sample_module.students.add(sample_user)

        # Create a sufficient mapping
        VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, sufficient=True, condition="pass")

        # Create a passing test score for the student
        Test_Score.objects.get_or_create(
            test=sample_test,
            user=sample_user,
            defaults={"score": 80.0, "passed": True},
        )

        sample_vital.check_vital(sample_user)

        assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_does_not_pass_student_without_results(self, sample_vital, sample_user, sample_test):
        """Test that check_vital does not mark a student as passed without any matching test scores.

        This validates the model operation performed by the create_vital_results admin action
        when a student has not met the requirements.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital, necessary=True, condition="pass")
            >>> vital.check_vital(user)
            >>> assert not VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, necessary=True, condition="pass")

        sample_vital.check_vital(sample_user)

        assert not VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()
