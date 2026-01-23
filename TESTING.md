# Running Pytest Tests

This directory contains pytest-based tests for the phas_vitals Django project.

## Setup

### 1. Install Test Dependencies

```bash
pip install -r requirements/test.txt
```

**Note**: The complete production environment requires additional packages that can be installed using the project's `environment.yaml` file with conda. The test requirements file provides the minimal dependencies needed to run the unit tests.

### 2. Run Tests

Run all tests:
```bash
pytest
```

Run tests from a specific app:
```bash
pytest apps/accounts/tests.py
pytest apps/vitals/tests.py
pytest apps/minerva/tests.py
```

Run a specific test class or method:
```bash
pytest apps/accounts/tests.py::TestCohort
pytest apps/accounts/tests.py::TestCohort::test_cohort_creation
```

Run tests with verbose output:
```bash
pytest -v
```

Run tests with coverage:
```bash
pytest --cov=apps --cov-report=html
```

## Test Structure

- `pytest.ini` - Pytest configuration file
- `conftest.py` - Shared fixtures and test configuration
- `phas_vitals/settings/test.py` - Django settings for testing
- `apps/*/tests.py` - Test files for each app

## Test Categories

Tests are marked with the following markers:
- `@pytest.mark.unit` - Unit tests for models and utilities
- `@pytest.mark.integration` - Integration tests for views and forms
- `@pytest.mark.slow` - Tests that take a long time to run

Run tests by marker:
```bash
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

## Fixtures

Common fixtures are defined in `conftest.py`:
- `sample_cohort` - Creates a test cohort
- `sample_programme` - Creates a test programme
- `sample_year` - Creates a test year
- `sample_user` - Creates a test user/account
- `sample_module` - Creates a test module
- `sample_test` - Creates a test Test instance
- `sample_vital` - Creates a test VITAL instance

## Troubleshooting

### Missing Dependencies

If you encounter `ModuleNotFoundError`, you may need to install additional dependencies. The full production environment requires packages like:
- django-baton
- django-ajax-selects  
- django-colorful
- django-htmx
- adminsortable2
- and many others

For complete compatibility, set up the full conda environment as described in the main README.rst.

### Database Issues

The tests use an in-memory SQLite database by default. If you need to use a persistent test database, modify the `DATABASES` setting in `phas_vitals/settings/test.py`.

## Writing New Tests

When adding new tests:

1. Follow the existing test structure in `apps/*/tests.py`
2. Use descriptive test names starting with `test_`
3. Add appropriate markers (`@pytest.mark.unit`, etc.)
4. Include docstrings with examples
5. Use fixtures from `conftest.py` where applicable
6. Follow British English spelling in documentation

Example test:

```python
@pytest.mark.django_db
@pytest.mark.unit
class TestMyModel:
    """Test the MyModel model."""

    def test_model_creation(self):
        """Test creating a model instance.
        
        Examples:
            >>> obj = MyModel.objects.create(name="Test")
            >>> assert obj.name == "Test"
        """
        obj = MyModel.objects.create(name="Test")
        assert obj.name == "Test"
```
