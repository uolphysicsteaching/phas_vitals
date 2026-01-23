"""Tests for the minerva app models and utilities."""

# Python imports
import pytest
import re

# Django imports
from django.core.exceptions import ValidationError
from django.utils import timezone as tz

# app imports
from .models import Module, module_validator, locate_named_group


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
        """Test locating a simple named group.
        
        Examples:
            >>> pattern = r"(?P<name>\\w+)"
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
        """Test locating a non-existent named group.
        
        Examples:
            >>> with pytest.raises(ValueError):
            ...     locate_named_group(r"(?P<name>\\w+)", "missing")
        """
        with pytest.raises(ValueError, match="Named group 'missing' not found"):
            locate_named_group(r"(?P<name>\w+)", "missing")

    def test_locate_named_group_with_substitution(self):
        """Test locating and substituting a named group.
        
        Examples:
            >>> pattern = r"(?P<name>\\w+)"
            >>> result = locate_named_group(pattern, "name", sub="replaced")
            >>> assert "replaced" in result
        """
        pattern = r"(?P<name>\w+)"
        result = locate_named_group(pattern, "name", sub="replaced")
        assert "replaced" in result


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
