"""Pytest configuration and fixtures for testing."""

# Python imports
import os
import sys
from pathlib import Path

# Setup Django settings before any Django imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "phas_vitals.settings.test")

# Add apps to Python path
DJANGO_ROOT_PATH = Path(__file__).parent / "phas_vitals"
PROJECT_ROOT_PATH = Path(__file__).parent
APPS_PATH = PROJECT_ROOT_PATH / "apps"
sys.path.insert(0, str(PROJECT_ROOT_PATH.absolute()))
sys.path.insert(0, str(APPS_PATH.absolute()))

# Django imports
# Django imports - let pytest-django handle setup
from django.contrib.auth import get_user_model

# external imports
import pytest


@pytest.fixture
def user_model():
    """Return the custom User model."""
    return get_user_model()


@pytest.fixture
def sample_status_code(db):
    """Create a sample status code for testing module enrolments.

    Module enrolments require a StatusCode with code ``'RE'`` (Registered) as the
    default status.  Without it, SQLite FK checks raise :class:`IntegrityError` at
    transaction teardown when enrolments are present.

    Args:
        db: The pytest database fixture.

    Returns:
        (StatusCode): A test StatusCode instance.
    """
    from minerva.models import StatusCode

    code, _ = StatusCode.objects.get_or_create(code="RE", defaults={"explanation": "Registered"})
    return code


@pytest.fixture
def sample_cohort(db):
    """Create a sample cohort for testing.

    Returns:
        (Cohort): A test cohort instance.
    """
    # external imports
    from accounts.models import Cohort

    cohort, _ = Cohort.objects.get_or_create(name="202425")
    return cohort


@pytest.fixture
def sample_programme(db):
    """Create a sample programme for testing.

    Returns:
        (Programme): A test programme instance.
    """
    # external imports
    from accounts.models import Programme

    programme, _ = Programme.objects.get_or_create(
        code="PHYS1234", defaults={"name": "Test Physics Programme", "local": True, "level": "B"}
    )
    return programme


@pytest.fixture
def sample_year(db):
    """Create a sample year for testing.

    Returns:
        (Year): A test year instance.
    """
    # external imports
    from accounts.models import Year

    year, _ = Year.objects.get_or_create(name="First Year", status="UG", defaults={"level": 1})
    return year


@pytest.fixture
def sample_user(db, sample_programme, sample_year):
    """Create a sample user/account for testing.

    Args:
        db: The pytest database fixture.
        sample_programme (Programme): A test programme instance.
        sample_year (Year): A test year instance.

    Returns:
        (Account): A test user instance.
    """
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username="testuser",
        defaults={
            "number": 123456,
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "programme": sample_programme,
            "year": sample_year,
        },
    )
    return user


@pytest.fixture
def sample_module(db, sample_cohort):
    """Create a sample module for testing.

    Args:
        db: The pytest database fixture.
        sample_cohort (Cohort): A test cohort instance.

    Returns:
        (Module): A test module instance.
    """
    # external imports
    from minerva.models import Module

    module, _ = Module.objects.get_or_create(
        code="PHAS1234",
        exam_code=1,
        defaults={
            "uuid": "test-uuid-12345",
            "name": "Test Module",
            "credits": 10,
            "level": 1,
            "year": sample_cohort,
            "semester": 1,
        },
    )
    return module


@pytest.fixture
def sample_test(db, sample_module):
    """Create a sample test for testing.

    Args:
        db: The pytest database fixture.
        sample_module (Module): A test module instance.

    Returns:
        (Test): A test Test instance.
    """
    # Django imports
    from django.utils import timezone as tz

    # external imports
    from minerva.models import Test

    test, _ = Test.objects.get_or_create(
        name="Sample Test",
        module=sample_module,
        defaults={
            "test_id": "sample-test-id",
            "description": "A test for testing",
            "passing_score": 50.0,
            "score_possible": 100.0,
            "release_date": tz.now(),
            "grading_due": tz.now() + tz.timedelta(days=7),
            "recommended_date": tz.now() + tz.timedelta(days=5),
        },
    )
    return test


@pytest.fixture
def sample_vital(db, sample_module):
    """Create a sample VITAL for testing.

    Args:
        db: The pytest database fixture.
        sample_module (Module): A test module instance.

    Returns:
        (VITAL): A test VITAL instance.
    """
    # external imports
    from vitals.models import VITAL

    vital, _ = VITAL.objects.get_or_create(
        name="Test VITAL",
        module=sample_module,
        defaults={"description": "A test VITAL for testing", "VITAL_ID": "V001"},
    )
    return vital
