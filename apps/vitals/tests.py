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

    def test_check_vital_sufficient_attempt_condition(self, sample_vital, sample_user, sample_test, sample_module):
        """Test that check_vital awards VITAL when a sufficient/attempt mapping is merely attempted.

        A mapping with sufficient=True and condition="attempt" should be satisfied by any
        result (pass or fail), not only by a passing score.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital, sufficient=True, condition="attempt")
            >>> Test_Score.objects.create(test=test, user=user, passed=False)
            >>> vital.check_vital(user)
            >>> assert VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from minerva.models import Test_Score

        sample_module.students.add(sample_user)
        VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, sufficient=True, condition="attempt")

        # Student attempted but did NOT pass
        Test_Score.objects.get_or_create(
            test=sample_test,
            user=sample_user,
            defaults={"score": 20.0, "passed": False},
        )

        sample_vital.check_vital(sample_user)

        assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_necessary_block_prevents_award(self, sample_vital, sample_user, sample_test, sample_module):
        """Test that an unmet necessary mapping prevents the VITAL being awarded.

        Even when the student has some results, a necessary condition that is not met must
        block the award.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital, necessary=True, condition="pass")
            >>> Test_Score.objects.create(test=test, user=user, passed=False)  # attempted, not passed
            >>> vital.check_vital(user)
            >>> assert not VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from minerva.models import Test_Score

        sample_module.students.add(sample_user)
        VITAL_Test_Map.objects.create(
            test=sample_test, vital=sample_vital, necessary=True, sufficient=False, condition="pass"
        )

        # Student attempted but did NOT pass the necessary test
        Test_Score.objects.get_or_create(
            test=sample_test,
            user=sample_user,
            defaults={"score": 20.0, "passed": False},
        )

        sample_vital.check_vital(sample_user)

        assert not VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_required_fraction_sum_awards_vital(
        self, sample_vital, sample_user, sample_test, sample_module, db
    ):
        """Test that VITAL is awarded when the sum of required_fractrion for met conditions reaches 1.0.

        Two mappings each with required_fractrion=0.5 should together satisfy the threshold
        when both are met.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.
            db: The pytest database fixture.

        Examples:
            >>> mapping1 = VITAL_Test_Map.objects.create(..., required_fractrion=0.5)
            >>> mapping2 = VITAL_Test_Map.objects.create(..., required_fractrion=0.5)
            >>> # pass both tests
            >>> vital.check_vital(user)
            >>> assert VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from django.utils import timezone as tz

        from minerva.models import Test, Test_Score

        sample_module.students.add(sample_user)

        test2, _ = Test.objects.get_or_create(
            name="Sample Test 2",
            module=sample_module,
            defaults={
                "test_id": "sample-test-id-2",
                "description": "A second test",
                "passing_score": 50.0,
                "score_possible": 100.0,
                "release_date": tz.now(),
                "grading_due": tz.now() + tz.timedelta(days=7),
                "recommended_date": tz.now() + tz.timedelta(days=5),
            },
        )

        VITAL_Test_Map.objects.create(
            test=sample_test, vital=sample_vital, sufficient=False, necessary=False, required_fractrion=0.5
        )
        VITAL_Test_Map.objects.create(
            test=test2, vital=sample_vital, sufficient=False, necessary=False, required_fractrion=0.5
        )

        # Student passes both tests
        Test_Score.objects.get_or_create(test=sample_test, user=sample_user, defaults={"score": 80.0, "passed": True})
        Test_Score.objects.get_or_create(test=test2, user=sample_user, defaults={"score": 80.0, "passed": True})

        sample_vital.check_vital(sample_user)

        assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_required_fraction_partial_does_not_award(
        self, sample_vital, sample_user, sample_test, sample_module, db
    ):
        """Test that VITAL is NOT awarded when the required_fractrion sum falls below 1.0.

        Two mappings each with required_fractrion=0.5 where only one is met should not
        satisfy the threshold.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.
            db: The pytest database fixture.

        Examples:
            >>> mapping1 = VITAL_Test_Map.objects.create(..., required_fractrion=0.5)
            >>> mapping2 = VITAL_Test_Map.objects.create(..., required_fractrion=0.5)
            >>> # pass only one test
            >>> vital.check_vital(user)
            >>> assert not VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from django.utils import timezone as tz

        from minerva.models import Test, Test_Score

        sample_module.students.add(sample_user)

        test2, _ = Test.objects.get_or_create(
            name="Sample Test 3",
            module=sample_module,
            defaults={
                "test_id": "sample-test-id-3",
                "description": "A third test",
                "passing_score": 50.0,
                "score_possible": 100.0,
                "release_date": tz.now(),
                "grading_due": tz.now() + tz.timedelta(days=7),
                "recommended_date": tz.now() + tz.timedelta(days=5),
            },
        )

        VITAL_Test_Map.objects.create(
            test=sample_test, vital=sample_vital, sufficient=False, necessary=False, required_fractrion=0.5
        )
        VITAL_Test_Map.objects.create(
            test=test2, vital=sample_vital, sufficient=False, necessary=False, required_fractrion=0.5
        )

        # Student passes only the first test
        Test_Score.objects.get_or_create(test=sample_test, user=sample_user, defaults={"score": 80.0, "passed": True})

        sample_vital.check_vital(sample_user)

        assert not VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_necessary_no_result_blocks_award(
        self, sample_vital, sample_user, sample_test, sample_module, db
    ):
        """Test that a necessary test with no result at all counts as not met and blocks the award.

        A student may have results for non-necessary VITAL tests but have never attempted the
        necessary test.  The necessary test having no result must be treated as "not positively
        passed", so the VITAL should be recorded as not passed rather than simply returning False.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.
            db: The pytest database fixture.
        """
        from django.utils import timezone as tz

        from minerva.models import Test, Test_Score

        sample_module.students.add(sample_user)

        # A second test that is non-necessary; the student will have a result for this one.
        non_necessary_test, _ = Test.objects.get_or_create(
            name="Sample Test 4",
            module=sample_module,
            defaults={
                "test_id": "sample-test-id-4",
                "description": "A non-necessary test",
                "passing_score": 50.0,
                "score_possible": 100.0,
                "release_date": tz.now(),
                "grading_due": tz.now() + tz.timedelta(days=7),
                "recommended_date": tz.now() + tz.timedelta(days=5),
            },
        )

        # sample_test is necessary; non_necessary_test is not.
        VITAL_Test_Map.objects.create(
            test=sample_test, vital=sample_vital, necessary=True, sufficient=False, condition="pass"
        )
        VITAL_Test_Map.objects.create(
            test=non_necessary_test, vital=sample_vital, necessary=False, sufficient=False, required_fractrion=0.5
        )

        # Student passes the non-necessary test only — no result at all for the necessary test.
        Test_Score.objects.get_or_create(
            test=non_necessary_test, user=sample_user, defaults={"score": 80.0, "passed": True}
        )

        sample_vital.check_vital(sample_user)

        # The necessary test was never attempted, so it counts as not met: VITAL must not be awarded.
        assert not VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()
        # A result should still be recorded (as not passed) because the student has engaged with the VITAL.
        assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=False).exists()


@pytest.mark.django_db
@pytest.mark.unit
class TestVITALCheckForQueryset:
    """Test the check_vital_for_queryset method on the VITAL model.

    Each test mirrors its counterpart in TestVITALAdminActions but exercises
    check_vital_for_queryset instead of check_vital so that identical semantics
    are verified for the bulk variant.
    """

    def test_check_vital_for_queryset_creates_result_for_passing_student(
        self, sample_vital, sample_user, sample_test, sample_module, sample_status_code
    ):
        """Test that check_vital_for_queryset creates a passing VITAL_Result for a sufficient test.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital, sufficient=True)
            >>> Test_Score.objects.create(test=test, user=user, passed=True)
            >>> updated = vital.check_vital_for_queryset(module.students.all())
            >>> assert VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from minerva.models import Test_Score

        sample_module.students.add(sample_user)
        VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, sufficient=True, condition="pass")
        score, _ = Test_Score.objects.get_or_create(
            test=sample_test,
            user=sample_user,
            defaults={"score": 80.0},
        )
        # Bypass Test_Score.save() which recalculates passed based on attempts.
        Test_Score.objects.filter(pk=score.pk).update(passed=True)

        sample_vital.check_vital_for_queryset(sample_module.students.all())

        assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_for_queryset_does_not_pass_student_without_results(
        self, sample_vital, sample_user, sample_test
    ):
        """Test that check_vital_for_queryset does not mark a student passed without test scores.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital, necessary=True)
            >>> vital.check_vital_for_queryset(Account.objects.filter(pk=user.pk))
            >>> assert not VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from accounts.models import Account

        VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, necessary=True, condition="pass")

        sample_vital.check_vital_for_queryset(Account.objects.filter(pk=sample_user.pk))

        assert not VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_for_queryset_sufficient_attempt_condition(
        self, sample_vital, sample_user, sample_test, sample_module, sample_status_code
    ):
        """Test that check_vital_for_queryset awards VITAL for a sufficient/attempt mapping.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital, sufficient=True, condition="attempt")
            >>> Test_Score.objects.create(test=test, user=user, passed=False)
            >>> vital.check_vital_for_queryset(module.students.all())
            >>> assert VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from minerva.models import Test_Score

        sample_module.students.add(sample_user)
        VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, sufficient=True, condition="attempt")
        score, _ = Test_Score.objects.get_or_create(
            test=sample_test,
            user=sample_user,
            defaults={"score": 20.0},
        )
        # Bypass Test_Score.save() which recalculates passed based on attempts.
        Test_Score.objects.filter(pk=score.pk).update(passed=False)

        sample_vital.check_vital_for_queryset(sample_module.students.all())

        assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_for_queryset_necessary_block_prevents_award(
        self, sample_vital, sample_user, sample_test, sample_module, sample_status_code
    ):
        """Test that an unmet necessary mapping prevents the VITAL being awarded.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.

        Examples:
            >>> mapping = VITAL_Test_Map.objects.create(test=test, vital=vital, necessary=True, condition="pass")
            >>> Test_Score.objects.create(test=test, user=user, passed=False)
            >>> vital.check_vital_for_queryset(module.students.all())
            >>> assert not VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from minerva.models import Test_Score

        sample_module.students.add(sample_user)
        VITAL_Test_Map.objects.create(
            test=sample_test, vital=sample_vital, necessary=True, sufficient=False, condition="pass"
        )
        score, _ = Test_Score.objects.get_or_create(
            test=sample_test,
            user=sample_user,
            defaults={"score": 20.0},
        )
        # Bypass Test_Score.save() which recalculates passed based on attempts.
        Test_Score.objects.filter(pk=score.pk).update(passed=False)

        sample_vital.check_vital_for_queryset(sample_module.students.all())

        assert not VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_for_queryset_required_fraction_sum_awards_vital(
        self, sample_vital, sample_user, sample_test, sample_module, db, sample_status_code
    ):
        """Test that VITAL is awarded when required_fraction sum reaches 1.0.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.
            db: The pytest database fixture.

        Examples:
            >>> mapping1 = VITAL_Test_Map.objects.create(..., required_fractrion=0.5)
            >>> mapping2 = VITAL_Test_Map.objects.create(..., required_fractrion=0.5)
            >>> # pass both tests
            >>> vital.check_vital_for_queryset(module.students.all())
            >>> assert VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from minerva.models import Test, Test_Score

        sample_module.students.add(sample_user)

        test2, _ = Test.objects.get_or_create(
            name="Sample Test QS2",
            module=sample_module,
            defaults={
                "test_id": "sample-test-qs-id-2",
                "description": "A second test for queryset tests",
                "passing_score": 50.0,
                "score_possible": 100.0,
                "release_date": tz.now(),
                "grading_due": tz.now() + tz.timedelta(days=7),
                "recommended_date": tz.now() + tz.timedelta(days=5),
            },
        )

        VITAL_Test_Map.objects.create(
            test=sample_test, vital=sample_vital, sufficient=False, necessary=False, required_fractrion=0.5
        )
        VITAL_Test_Map.objects.create(
            test=test2, vital=sample_vital, sufficient=False, necessary=False, required_fractrion=0.5
        )

        Test_Score.objects.get_or_create(test=sample_test, user=sample_user, defaults={"score": 80.0})
        Test_Score.objects.filter(test=sample_test, user=sample_user).update(passed=True)
        score2, _ = Test_Score.objects.get_or_create(test=test2, user=sample_user, defaults={"score": 80.0})
        Test_Score.objects.filter(pk=score2.pk).update(passed=True)

        sample_vital.check_vital_for_queryset(sample_module.students.all())

        assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_for_queryset_required_fraction_partial_does_not_award(
        self, sample_vital, sample_user, sample_test, sample_module, db, sample_status_code
    ):
        """Test that VITAL is NOT awarded when required_fraction sum is below 1.0.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.
            db: The pytest database fixture.

        Examples:
            >>> mapping1 = VITAL_Test_Map.objects.create(..., required_fractrion=0.5)
            >>> mapping2 = VITAL_Test_Map.objects.create(..., required_fractrion=0.5)
            >>> # pass only one test
            >>> vital.check_vital_for_queryset(module.students.all())
            >>> assert not VITAL_Result.objects.filter(vital=vital, user=user, passed=True).exists()
        """
        from minerva.models import Test, Test_Score

        sample_module.students.add(sample_user)

        test2, _ = Test.objects.get_or_create(
            name="Sample Test QS3",
            module=sample_module,
            defaults={
                "test_id": "sample-test-qs-id-3",
                "description": "A third test for queryset tests",
                "passing_score": 50.0,
                "score_possible": 100.0,
                "release_date": tz.now(),
                "grading_due": tz.now() + tz.timedelta(days=7),
                "recommended_date": tz.now() + tz.timedelta(days=5),
            },
        )

        VITAL_Test_Map.objects.create(
            test=sample_test, vital=sample_vital, sufficient=False, necessary=False, required_fractrion=0.5
        )
        VITAL_Test_Map.objects.create(
            test=test2, vital=sample_vital, sufficient=False, necessary=False, required_fractrion=0.5
        )

        # Student passes only the first test.
        score1, _ = Test_Score.objects.get_or_create(test=sample_test, user=sample_user, defaults={"score": 80.0})
        Test_Score.objects.filter(pk=score1.pk).update(passed=True)

        sample_vital.check_vital_for_queryset(sample_module.students.all())

        assert not VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()

    def test_check_vital_for_queryset_necessary_no_result_blocks_award(
        self, sample_vital, sample_user, sample_test, sample_module, db, sample_status_code
    ):
        """Test that a necessary test with no result at all blocks the award.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.
            db: The pytest database fixture.
        """
        from minerva.models import Test, Test_Score

        sample_module.students.add(sample_user)

        non_necessary_test, _ = Test.objects.get_or_create(
            name="Sample Test QS4",
            module=sample_module,
            defaults={
                "test_id": "sample-test-qs-id-4",
                "description": "A non-necessary test for queryset tests",
                "passing_score": 50.0,
                "score_possible": 100.0,
                "release_date": tz.now(),
                "grading_due": tz.now() + tz.timedelta(days=7),
                "recommended_date": tz.now() + tz.timedelta(days=5),
            },
        )

        VITAL_Test_Map.objects.create(
            test=sample_test, vital=sample_vital, necessary=True, sufficient=False, condition="pass"
        )
        VITAL_Test_Map.objects.create(
            test=non_necessary_test, vital=sample_vital, necessary=False, sufficient=False, required_fractrion=0.5
        )

        # Student passes only the non-necessary test; no result for the necessary test.
        nn_score, _ = Test_Score.objects.get_or_create(
            test=non_necessary_test, user=sample_user, defaults={"score": 80.0}
        )
        Test_Score.objects.filter(pk=nn_score.pk).update(passed=True)

        sample_vital.check_vital_for_queryset(sample_module.students.all())

        assert not VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()
        assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=False).exists()

    def test_check_vital_for_queryset_multiple_users(self, sample_vital, sample_test, sample_module, db, sample_status_code):
        """Test that check_vital_for_queryset handles multiple users correctly in one call.

        One user passes the sufficient test; a second user has no result.  Only the
        first user should receive a passing VITAL_Result.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.
            db: The pytest database fixture.
        """
        from accounts.models import Account
        from minerva.models import Test_Score

        user1, _ = Account.objects.get_or_create(
            username="qs_user1",
            defaults={"number": 111001, "email": "qs_user1@example.com", "first_name": "QS", "last_name": "One"},
        )
        user2, _ = Account.objects.get_or_create(
            username="qs_user2",
            defaults={"number": 111002, "email": "qs_user2@example.com", "first_name": "QS", "last_name": "Two"},
        )

        sample_module.students.add(user1, user2)
        VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, sufficient=True, condition="pass")

        # Only user1 passes the test.
        u1_score, _ = Test_Score.objects.get_or_create(test=sample_test, user=user1, defaults={"score": 80.0})
        Test_Score.objects.filter(pk=u1_score.pk).update(passed=True)

        count = sample_vital.check_vital_for_queryset(sample_module.students.all())

        # user1 should be recorded as passing; user2 has no result so nothing is recorded.
        assert VITAL_Result.objects.filter(vital=sample_vital, user=user1, passed=True).exists()
        assert not VITAL_Result.objects.filter(vital=sample_vital, user=user2).exists()
        assert count == 1

    def test_check_vital_for_queryset_returns_count_of_changes(
        self, sample_vital, sample_user, sample_test, sample_module, sample_status_code
    ):
        """Test that check_vital_for_queryset returns the number of records changed.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.

        Examples:
            >>> count = vital.check_vital_for_queryset(module.students.all())
            >>> assert count == 1  # one record created or updated
        """
        from minerva.models import Test_Score

        sample_module.students.add(sample_user)
        VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, sufficient=True, condition="pass")
        score, _ = Test_Score.objects.get_or_create(
            test=sample_test,
            user=sample_user,
            defaults={"score": 80.0},
        )
        Test_Score.objects.filter(pk=score.pk).update(passed=True)

        count = sample_vital.check_vital_for_queryset(sample_module.students.all())

        assert count == 1

        # Second call with no change should return 0.
        count2 = sample_vital.check_vital_for_queryset(sample_module.students.all())
        assert count2 == 0

    def test_check_vital_for_queryset_empty_queryset(self, sample_vital, sample_module):
        """Test that check_vital_for_queryset returns 0 for an empty user queryset.

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_module (Module): A test module instance.

        Examples:
            >>> count = vital.check_vital_for_queryset(Account.objects.none())
            >>> assert count == 0
        """
        from accounts.models import Account

        count = sample_vital.check_vital_for_queryset(Account.objects.none())

        assert count == 0

    def test_check_vital_for_queryset_updates_existing_result(
        self, sample_vital, sample_user, sample_test, sample_module, sample_status_code
    ):
        """Test that check_vital_for_queryset updates an existing VITAL_Result without raising FieldError.

        Regression test for the FieldError "Cannot update when ordering by an aggregate" that
        occurred when bulk_update was called through a manager whose queryset ordered by an
        aggregate annotation (e.g. Min(release_date)).

        Args:
            sample_vital (VITAL): A test VITAL instance.
            sample_user (Account): A test user instance.
            sample_test (Test): A test Test instance.
            sample_module (Module): A test module instance.
            sample_status_code: A test status code fixture.

        Examples:
            >>> # Pre-create a failing result, then add a passing score and re-check.
            >>> VITAL_Result.objects.create(vital=sample_vital, user=sample_user, passed=False)
            >>> Test_Score.objects.filter(pk=score.pk).update(passed=True)
            >>> count = sample_vital.check_vital_for_queryset(sample_module.students.all())
            >>> assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()
        """
        from minerva.models import Test_Score

        sample_module.students.add(sample_user)
        VITAL_Test_Map.objects.create(test=sample_test, vital=sample_vital, sufficient=True, condition="pass")

        # Pre-create a VITAL_Result with passed=False so that the next call will trigger an UPDATE
        # (via bulk_update) rather than a CREATE (via bulk_create).
        VITAL_Result.objects.create(vital=sample_vital, user=sample_user, passed=False)

        # Now give the user a passing score so the VITAL should be awarded.
        score, _ = Test_Score.objects.get_or_create(test=sample_test, user=sample_user, defaults={"score": 80.0})
        Test_Score.objects.filter(pk=score.pk).update(passed=True)

        # This call must not raise FieldError and must update the existing record.
        count = sample_vital.check_vital_for_queryset(sample_module.students.all())

        assert count == 1
        assert VITAL_Result.objects.filter(vital=sample_vital, user=sample_user, passed=True).exists()
