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
