"""Tests for tutorial import-export resources."""

# Python imports
from unittest.mock import patch

# Django imports
from django.test import TestCase

# external imports
from accounts.models import Account, Cohort
from import_export.exceptions import ImportError
from minerva.models import Module, ModuleEnrollment, StatusCode
from tablib import Dataset

# app imports
from .models import Tutorial, TutorialAssignment
from .resources import TutorialAssignmentResource


class TutorialAssignmentResourceTests(TestCase):
    """Test direct and adaptive tutorial-assignment imports."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = Cohort.objects.create(name="202627")
        cls.other_cohort = Cohort.objects.create(name="202526")
        cls.tutor = Account.objects.create_user(
            username="resource-tutor",
            number=999901,
            first_name="Terry",
            last_name="Tutor",
            is_staff=True,
        )
        cls.other_tutor = Account.objects.create_user(
            username="resource-other-tutor",
            number=999902,
            first_name="Olive",
            last_name="Other",
            is_staff=True,
        )
        cls.student = Account.objects.create_user(
            username="resource-student",
            number=29999001,
            first_name="Sam",
            last_name="Student",
        )
        cls.other_student = Account.objects.create_user(
            username="resource-other-student",
            number=29999002,
            first_name="Alice",
            last_name="Example",
        )
        cls.tutorial = Tutorial.objects.create(code="DIRECT", tutor=cls.tutor, cohort=cls.cohort)

    def import_rows(self, *rows, headers, raise_errors=True):
        """Import rows through the tutorial-assignment resource."""
        return TutorialAssignmentResource().import_data(
            Dataset(*rows, headers=headers),
            dry_run=False,
            raise_errors=raise_errors,
        )

    def test_existing_direct_mapping_remains_supported(self):
        """Import the existing tutorial-code and student-username columns."""
        result = self.import_rows(
            [self.tutorial.code, self.student.username],
            headers=["tutorial", "student"],
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(TutorialAssignment.objects.get(student=self.student).tutorial, self.tutorial)

    def test_student_id_and_column_names_are_case_insensitive(self):
        """Resolve an account number from a case-insensitive Student ID heading."""
        result = self.import_rows(
            [self.student.number, self.tutorial.code],
            headers=["sTuDeNt Id", "TuToRiAl"],
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(TutorialAssignment.objects.get(student=self.student).tutorial, self.tutorial)

    def test_student_name_aliases_are_case_insensitive(self):
        """Resolve a student through the Surname and First Name aliases."""
        result = self.import_rows(
            [self.other_student.last_name.lower(), self.other_student.first_name.lower(), self.tutorial.code],
            headers=["sUrNaMe", "fIrSt nAmE", "TUTORIAL"],
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(TutorialAssignment.objects.get(student=self.other_student).tutorial, self.tutorial)

    def test_existing_assignment_supplies_cohort_and_is_replaced(self):
        """Move an assigned student to the imported tutor's group in the same cohort."""
        old_tutorial = Tutorial.objects.create(code="OLD", tutor=self.other_tutor, cohort=self.other_cohort)
        existing = TutorialAssignment.objects.create(tutorial=old_tutorial, student=self.student)
        target = Tutorial.objects.create(
            code=f"_{self.tutor.initials}_{self.other_cohort.pk}",
            tutor=self.tutor,
            cohort=self.other_cohort,
        )

        result = self.import_rows(
            [self.student.number, self.tutor.initials],
            headers=["STUDENT ID", "tUtOr"],
        )

        self.assertFalse(result.has_errors())
        assignment = TutorialAssignment.objects.get(student=self.student)
        self.assertNotEqual(assignment.pk, existing.pk)
        self.assertEqual(assignment.tutorial, target)
        self.assertEqual(TutorialAssignment.objects.filter(student=self.student).count(), 1)

    def test_dry_run_does_not_replace_an_existing_assignment(self):
        """Roll back assignment replacement during import preview."""
        old_tutorial = Tutorial.objects.create(code="DRY-OLD", tutor=self.other_tutor, cohort=self.other_cohort)
        existing = TutorialAssignment.objects.create(tutorial=old_tutorial, student=self.student)
        Tutorial.objects.create(
            code=f"_{self.tutor.initials}_{self.other_cohort.pk}",
            tutor=self.tutor,
            cohort=self.other_cohort,
        )
        dataset = Dataset(
            [self.student.number, self.tutor.initials],
            headers=["Student ID", "Tutor"],
        )

        result = TutorialAssignmentResource().import_data(
            dataset,
            dry_run=True,
            raise_errors=True,
            use_transactions=True,
        )

        self.assertFalse(result.has_errors())
        existing.refresh_from_db()
        self.assertEqual(existing.tutorial, old_tutorial)
        self.assertEqual(TutorialAssignment.objects.filter(student=self.student).count(), 1)

    def test_first_module_enrolment_supplies_cohort_and_tutor_can_fall_back_to_surname(self):
        """Infer a new assignment from the first enrolment and tutor surname."""
        status = StatusCode.objects.create(code="RE")
        module = Module.objects.create(
            uuid="resource-module",
            code="PHAS1000",
            name="Resource module",
            year=self.cohort,
        )
        ModuleEnrollment.objects.create(module=module, student=self.student, status=status)
        target = Tutorial.objects.create(
            code=f"_{self.tutor.initials}_{self.cohort.pk}",
            tutor=self.tutor,
            cohort=self.cohort,
        )

        result = self.import_rows(
            [self.student.number, f"Unmatched Given Names {self.tutor.last_name}"],
            headers=["Student ID", "Tutor"],
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(TutorialAssignment.objects.get(student=self.student).tutorial, target)

    def test_tutor_matching_prefers_regular_staff_account_over_superuser_account(self):
        """Exclude a tutor's superuser identity from full-name and surname matching."""
        Account.objects.create_user(
            username="resource-tutor-admin",
            number=999903,
            first_name=self.tutor.first_name,
            last_name=self.tutor.last_name,
            is_staff=True,
            is_superuser=True,
        )
        resource = TutorialAssignmentResource()

        self.assertEqual(resource._resolve_tutor("Terry Tutor", {}), self.tutor)
        self.assertEqual(resource._resolve_tutor("Unmatched Given Names Tutor", {}), self.tutor)

    def test_missing_inferred_tutorial_group_is_an_import_error(self):
        """Reject an inferred code when its tutorial group does not exist."""
        status = StatusCode.objects.create(code="RE")
        module = Module.objects.create(
            uuid="missing-tutorial-module",
            code="PHAS2000",
            name="Missing tutorial module",
            year=self.cohort,
        )
        ModuleEnrollment.objects.create(module=module, student=self.student, status=status)

        with self.assertRaisesMessage(ImportError, "does not exist"):
            self.import_rows(
                [self.student.number, self.tutor.initials],
                headers=["Student ID", "Tutor"],
            )

        self.assertFalse(TutorialAssignment.objects.filter(student=self.student).exists())

    def test_multiple_inferred_tutorial_groups_are_an_import_error(self):
        """Reject an inferred code if its tutorial lookup is ambiguous."""
        status = StatusCode.objects.create(code="RE")
        module = Module.objects.create(
            uuid="ambiguous-tutorial-module",
            code="PHAS3000",
            name="Ambiguous tutorial module",
            year=self.cohort,
        )
        ModuleEnrollment.objects.create(module=module, student=self.student, status=status)

        with (
            patch(
                "tutorial.resources.Tutorial.objects.get",
                side_effect=Tutorial.MultipleObjectsReturned,
            ),
            self.assertRaisesMessage(ImportError, "Multiple tutorial groups"),
        ):
            self.import_rows(
                [self.student.number, self.tutor.initials],
                headers=["Student ID", "Tutor"],
            )
