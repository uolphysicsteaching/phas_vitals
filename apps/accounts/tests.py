"""Tests for the accounts app models."""

# Python imports
import pytest

# Django imports
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.utils import timezone

# app imports
from .models import Cohort, Programme, Year


@pytest.mark.django_db
@pytest.mark.unit
class TestCohort:
    """Test the Cohort model."""

    def test_cohort_creation(self):
        """Test creating a cohort.
        
        Examples:
            >>> cohort = Cohort.objects.create(name="202425")
            >>> assert str(cohort) == "2024/25"
        """
        cohort = Cohort.objects.create(name="202425")
        assert cohort.name == "202425"
        assert str(cohort) == "2024/25"

    def test_cohort_str_representation(self):
        """Test string representation of cohort.
        
        Examples:
            >>> cohort = Cohort.objects.create(name="202425")
            >>> assert str(cohort) == "2024/25"
        """
        cohort = Cohort.objects.create(name="202425")
        assert str(cohort) == "2024/25"

    def test_cohort_str_with_invalid_format(self):
        """Test string representation with non-numeric name.
        
        Examples:
            >>> cohort = Cohort.objects.create(name="test")
            >>> assert str(cohort) == "test"
        """
        cohort = Cohort.objects.create(name="test")
        assert str(cohort) == "test"

    def test_cohort_int_conversion(self):
        """Test integer conversion of cohort.
        
        Examples:
            >>> cohort = Cohort.objects.create(name="202425")
            >>> assert int(cohort) == 202425
        """
        cohort = Cohort.objects.create(name="202425")
        assert int(cohort) == 202425

    def test_cohort_int_with_invalid_format(self):
        """Test integer conversion with non-numeric name.
        
        Examples:
            >>> cohort = Cohort.objects.create(name="test")
            >>> assert int(cohort) is None
        """
        cohort = Cohort.objects.create(name="test")
        assert int(cohort) is None

    def test_cohort_current(self):
        """Test getting current cohort.
        
        Examples:
            >>> cohort = Cohort.current
            >>> assert cohort is not None
        """
        cohort = Cohort.current
        assert cohort is not None
        assert isinstance(cohort, Cohort)

    def test_cohort_get_with_cohort_object(self):
        """Test getting cohort with a Cohort object.
        
        Examples:
            >>> cohort = Cohort.objects.create(name="202425")
            >>> result = Cohort.get(cohort)
            >>> assert result == cohort
        """
        cohort = Cohort.objects.create(name="202425")
        result = Cohort.get(cohort)
        assert result == cohort

    def test_cohort_get_with_string(self):
        """Test getting cohort with a string.
        
        Examples:
            >>> cohort = Cohort.objects.create(name="202425")
            >>> result = Cohort.get("2024/25")
            >>> assert result == cohort
        """
        cohort = Cohort.objects.create(name="202425")
        result = Cohort.get("2024/25")
        assert result == cohort

    def test_cohort_get_with_int(self):
        """Test getting cohort with an integer.
        
        Examples:
            >>> cohort = Cohort.objects.create(name="202425")
            >>> result = Cohort.get(202425)
            >>> assert result == cohort
        """
        cohort = Cohort.objects.create(name="202425")
        result = Cohort.get(202425)
        assert result == cohort


@pytest.mark.django_db
@pytest.mark.unit
class TestProgramme:
    """Test the Programme model."""

    def test_programme_creation(self):
        """Test creating a programme.
        
        Examples:
            >>> prog = Programme.objects.create(code="PHYS1234", name="Test Programme")
            >>> assert prog.code == "PHYS1234"
        """
        programme = Programme.objects.create(
            code="PHYS1234", name="Test Physics Programme", local=True, level="B"
        )
        assert programme.code == "PHYS1234"
        assert programme.name == "Test Physics Programme"
        assert programme.local is True

    def test_programme_str_representation(self):
        """Test string representation of programme.
        
        Examples:
            >>> prog = Programme.objects.create(code="PHYS1234", name="Test Programme")
            >>> assert str(prog) == "Test Programme (PHYS1234)"
        """
        programme = Programme.objects.create(code="PHYS1234", name="Test Physics Programme")
        assert str(programme) == "Test Physics Programme (PHYS1234)"


@pytest.mark.django_db
@pytest.mark.unit
class TestYear:
    """Test the Year model."""

    def test_year_creation(self):
        """Test creating a year.
        
        Examples:
            >>> year = Year.objects.create(name="First Year", status="UG", level=1)
            >>> assert year.name == "First Year"
        """
        year = Year.objects.create(name="First Year", status="UG", level=1)
        assert year.name == "First Year"
        assert year.status == "UG"
        assert year.level == 1

    def test_year_str_representation(self):
        """Test string representation of year.
        
        Examples:
            >>> year = Year.objects.create(name="First Year", status="UG", level=1)
            >>> assert str(year) == "First Year, UG"
        """
        year = Year.objects.create(name="First Year", status="UG", level=1)
        assert str(year) == "First Year, UG"

    def test_year_natural_key(self):
        """Test natural key of year.
        
        Examples:
            >>> year = Year.objects.create(name="First Year", status="UG", level=1)
            >>> assert year.natural_key() == "First Year, UG"
        """
        year = Year.objects.create(name="First Year", status="UG", level=1)
        assert year.natural_key() == "First Year, UG"

    def test_year_get_by_natural_key(self):
        """Test getting year by natural key.
        
        Examples:
            >>> year = Year.objects.create(name="First Year", status="UG", level=1)
            >>> result = Year.objects.get_by_natural_key("First Year, UG")
            >>> assert result == year
        """
        year = Year.objects.create(name="First Year", status="UG", level=1)
        result = Year.objects.get_by_natural_key("First Year, UG")
        assert result == year

    def test_year_unique_constraint(self):
        """Test unique constraint on year name and status.
        
        Examples:
            >>> Year.objects.create(name="First Year", status="UG", level=1)
            >>> with pytest.raises(IntegrityError):
            ...     Year.objects.create(name="First Year", status="UG", level=2)
        """
        Year.objects.create(name="First Year", status="UG", level=1)
        with pytest.raises(IntegrityError):
            Year.objects.create(name="First Year", status="UG", level=2)


@pytest.mark.django_db
@pytest.mark.unit
class TestAccount:
    """Test the Account model."""

    def test_account_creation(self, sample_programme, sample_year):
        """Test creating an account.
        
        Args:
            sample_programme (Programme): A test programme instance.
            sample_year (Year): A test year instance.
            
        Examples:
            >>> user = User.objects.create(username="testuser", number=123456)
            >>> assert user.username == "testuser"
        """
        User = get_user_model()
        user = User.objects.create(
            username="testuser",
            number=123456,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            programme=sample_programme,
            year=sample_year,
        )
        assert user.username == "testuser"
        assert user.number == 123456
        assert user.programme == sample_programme
        assert user.year == sample_year

    def test_account_unique_number(self):
        """Test that account numbers are unique.
        
        Examples:
            >>> User.objects.create(username="user1", number=123456)
            >>> with pytest.raises(IntegrityError):
            ...     User.objects.create(username="user2", number=123456)
        """
        User = get_user_model()
        User.objects.create(username="user1", number=123456)
        with pytest.raises(IntegrityError):
            User.objects.create(username="user2", number=123456)

    def test_account_ordering(self):
        """Test account ordering by last name and first name.
        
        Examples:
            >>> User.objects.create(username="user1", number=1, last_name="Zebra")
            >>> User.objects.create(username="user2", number=2, last_name="Apple")
            >>> users = list(User.objects.all())
            >>> assert users[0].last_name == "Apple"
        """
        User = get_user_model()
        User.objects.create(username="user1", number=111111, last_name="Zebra", first_name="Adam")
        User.objects.create(username="user2", number=222222, last_name="Apple", first_name="Bob")
        users = list(User.objects.all())
        assert users[0].last_name == "Apple"
        assert users[1].last_name == "Zebra"
