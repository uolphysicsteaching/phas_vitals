# Known Bugs and Issues

## Pre-existing test failures in `TestVITALAdminActions`

**File:** `apps/vitals/tests.py` – class `TestVITALAdminActions`

**Symptoms:**

Several tests in `TestVITALAdminActions` fail or error when run with `--no-migrations`:

- `test_check_vital_creates_result_for_passing_student` – assertion fails (VITAL_Result not
  created with `passed=True`).
- `test_check_vital_required_fraction_sum_awards_vital` – assertion fails.
- Various tests that call `sample_module.students.add(sample_user)` – teardown
  `IntegrityError` because the default `ModuleEnrollment.status_id` value (`'RE'`) has no
  corresponding `StatusCode` row in the test database.

**Root causes:**

1. `Test_Score.save()` recalculates `passed` via `check_passed()`.  When no `Test_Attempt`
   records exist, `check_passed()` always returns `passed=False`, regardless of the value
   supplied to `get_or_create(defaults={'passed': True})`.  The tests create scores with
   `passed=True` in `defaults` but the custom `save()` resets the value to `False`.

2. `ModuleEnrollment` has `status = ForeignKey(StatusCode, default='RE')`.  The test
   database has no `StatusCode` rows, so Django's FK check raises `IntegrityError` during
   teardown when enrolled students are present.

**Fix:**

Apply the same workarounds used in `TestVITALCheckForQueryset`:

1. After creating a `Test_Score`, use `.update(passed=True)` to bypass the custom `save()`::

       score, _ = Test_Score.objects.get_or_create(test=..., user=..., defaults={"score": 80.0})
       Test_Score.objects.filter(pk=score.pk).update(passed=True)

2. Add the `sample_status_code` fixture (defined in `conftest.py`) as a parameter to every
   test method that calls `module.students.add(...)`.
