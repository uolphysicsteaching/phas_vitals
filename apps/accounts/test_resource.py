"""Tests for account import-export resources."""

# Django imports
from django.contrib.auth.models import Group
from django.test import TestCase

# external imports
from accounts.models import Account, Cohort, Programme, School, Year
from accounts.resource import UserResource
from minerva.models import Module, ModuleEnrollment, StatusCode
from tablib import Dataset
from tutorial.models import Tutorial, TutorialAssignment


class TestUserResource(TestCase):
    """Test adaptive account imports."""

    def test_banner_rows_create_programmes_accounts_and_module_enrolments(self):
        """Import full Banner rows, including enrolments on a parent and its sub-modules."""
        Group.objects.create(name="Student")
        school = School.objects.create(code="PHAS", name="Physics and Astronomy")
        year = Year.objects.create(name="First Year", status="UG", level=1)
        cohort = Cohort.objects.create(name="202627")
        status = StatusCode.objects.create(code="RE", explanation="Registered")
        parent = Module.objects.create(
            uuid="parent",
            courseId="40949",
            code="PHAS1000",
            name="Physics 1",
            year=cohort,
        )
        children = [
            Module.objects.create(
                uuid=f"child-{index}",
                courseId=f"child-{index}",
                code=f"PHAS100{index + 1}",
                name=f"Physics 1 unit {index}",
                year=cohort,
                parent_module=parent,
            )
            for index in range(2)
        ]
        dataset = Dataset(
            *[
                [
                    "202627",
                    40949.0,
                    "PHAS100001",
                    3,
                    "28/09/2026",
                    "19/06/2027",
                    "01",
                    "RE",
                    "26/08/2026 19:05",
                    "O",
                    "Overseas Rated Student",
                    202140781,
                    "Mohammad",
                    "Alazemi",
                    "nxjj0308@leeds.ac.uk",
                    "EL",
                    "23/09/2026",
                    "BS-PHYS",
                    "Physics",
                    "PHAS",
                ],
                [
                    "202627",
                    40949.0,
                    "PHAS100001",
                    3,
                    "28/09/2026",
                    "19/06/2027",
                    "01",
                    "RE",
                    "28/08/2026 19:01",
                    "O",
                    "Overseas Rated Student",
                    202158468,
                    "Abdulrahman",
                    "Alghamdi",
                    "blms0941@leeds.ac.uk",
                    "EL",
                    "23/09/2026",
                    "BS-PHYS/AP",
                    "Physics with Astrophysics",
                    "PHAS",
                ],
            ],
            headers=[
                "Term",
                "CRN",
                "Modulecode",
                "PTRM",
                "PTRM_start",
                "PTRM_end",
                "Student_Year",
                "RSTS",
                "Enrolment_RSTS__date",
                "RESD_Code",
                "RESD",
                "ID",
                "FName",
                "LName",
                "ISS_Email",
                "ESTS",
                "StartDate",
                "Programme",
                "Prog_Desc",
                "Dept",
            ],
        )

        result = UserResource().import_data(dataset, dry_run=False, raise_errors=True)

        assert not result.has_errors()
        student = Account.objects.get(username="nxjj0308")
        assert student.email == "nxjj0308@leeds.ac.uk"
        assert student.number == 202140781
        assert student.first_name == "Mohammad"
        assert student.last_name == "Alazemi"
        assert student.programme == Programme.objects.get(code="BS-PHYS", name="Physics")
        assert student.school == school
        assert student.year == year
        assert student.registration_status == "EL"
        other_student = Account.objects.get(username="blms0941")
        assert other_student.number == 202158468
        assert other_student.first_name == "Abdulrahman"
        assert other_student.last_name == "Alghamdi"
        assert other_student.programme == Programme.objects.get(code="BS-PHYS/AP", name="Physics with Astrophysics")
        expected_module_ids = {
            parent.pk,
            *(child.pk for child in children),
        }
        for imported_student in (student, other_student):
            assert (
                set(ModuleEnrollment.objects.filter(student=imported_student).values_list("module_id", flat=True))
                == expected_module_ids
            )
            assert not ModuleEnrollment.objects.filter(student=imported_student).exclude(status=status).exists()

    def test_banner_row_updates_existing_enrolments_without_duplicates(self):
        """Repeated rows update enrolment status without making duplicate records."""
        Group.objects.create(name="Student")
        Year.objects.create(name="First Year", status="UG", level=1)
        cohort = Cohort.objects.create(name="202627")
        StatusCode.objects.create(code="RE", explanation="Registered")
        withdrawn = StatusCode.objects.create(code="WD", explanation="Withdrawn")
        module = Module.objects.create(
            uuid="module",
            courseId="40949",
            code="PHAS1000",
            name="Physics 1",
            year=cohort,
        )
        Programme.objects.create(code="BS-PHYS", name="Physics")
        row = [
            "202627",
            "40949",
            "PHAS100001",
            "01",
            "RE",
            202000001,
            "Mohammad",
            "Alazemi",
            "nxjj0308@leeds.ac.uk",
            "EL",
            "BS-PHYS",
            "Physics",
        ]
        headers = [
            "Term",
            "CRN",
            "Modulecode",
            "Student_Year",
            "RSTS",
            "ID",
            "FName",
            "LName",
            "ISS_Email",
            "ESTS",
            "Programme",
            "Prog_Desc",
        ]
        resource = UserResource()
        resource.import_data(Dataset(row, headers=headers), dry_run=False, raise_errors=True)
        student = Account.objects.get(username="nxjj0308")
        student.is_active = False
        student.save(update_fields=["is_active"])
        row[4] = "WD"

        resource.import_data(Dataset(row, headers=headers), dry_run=False, raise_errors=True)

        enrolment = ModuleEnrollment.objects.get(module=module)
        student.refresh_from_db()
        assert enrolment.status == withdrawn
        assert student.is_active is True
        assert ModuleEnrollment.objects.filter(module=module).count() == 1

    def test_module_code_without_exam_suffix_is_unchanged(self):
        """Retain a standard module code during normalisation."""
        assert UserResource._normalise_module_code("PHAS1000") == "PHAS1000"

    def test_module_code_with_exam_suffix_is_trimmed(self):
        """Remove an exam suffix from a Banner module code during normalisation."""
        assert UserResource._normalise_module_code("PHAS100001") == "PHAS1000"

    def test_masters_module_code_without_exam_suffix_is_unchanged(self):
        """Retain a canonical master's module code during normalisation."""
        assert UserResource._normalise_module_code("PHAS5000M") == "PHAS5000M"

    def test_masters_module_code_with_exam_suffix_is_trimmed(self):
        """Remove an exam suffix from a canonical master's module code."""
        assert UserResource._normalise_module_code("PHAS5000M01") == "PHAS5000M"

    def test_shortened_masters_module_code_is_restored(self):
        """Restore the omitted zero in a shortened Banner master's module code."""
        assert UserResource._normalise_module_code("PHAS500M01") == "PHAS5000M"

    def test_apt_import_creates_tutorial_and_assigns_first_year_student(self):
        """Resolve an imported APT and create the student's tutorial assignment."""
        year = Year.objects.create(name="First Year", status="UG", level=1)
        tutor = Account.objects.create_user(
            username="tutor",
            number=100000001,
            first_name="Alex",
            last_name="Tutor",
            email="alex.tutor@leeds.ac.uk",
            is_staff=True,
        )
        dataset = Dataset(
            [
                "student",
                202000001,
                "Student",
                "One",
                "student@leeds.ac.uk",
                year.level,
                "202627",
                tutor.initials,
            ],
            headers=["username", "number", "first_name", "last_name", "email", "year", "Term", "apt"],
        )

        result = UserResource().import_data(dataset, dry_run=False, raise_errors=True)

        assert not result.has_errors()
        tutorial = Tutorial.objects.get(code=f"_{tutor.initials}_202627")
        assert tutorial.tutor == tutor
        assert tutorial.cohort == Cohort.objects.get(name="202627")
        assert TutorialAssignment.objects.get(student__username="student").tutorial == tutorial

    def test_apt_widget_matches_all_supported_staff_name_formats(self):
        """Resolve initials, usernames, conventional names, and account display names."""
        tutor = Account.objects.create_user(
            username="aptuser",
            number=100000001,
            title="Dr",
            first_name="Alex",
            givenName="Alexander",
            last_name="Tutor",
            email="alex.tutor@leeds.ac.uk",
            is_staff=True,
        )
        Account.objects.create_user(
            username="student-name-match",
            number=200000001,
            first_name="Alex",
            last_name="Tutor",
            email="student@leeds.ac.uk",
        )
        widget = UserResource().fields["apt"].widget
        values = [
            tutor.initials,
            tutor.username,
            f"{tutor.last_name}, {tutor.first_name}",
            f"{tutor.first_name} {tutor.last_name}",
            tutor.display_name,
            tutor.formal_name,
        ]

        for value in values:
            with self.subTest(value=value):
                assert widget.clean(value) == tutor

    def test_apt_widget_matches_multi_word_first_and_last_names(self):
        """Resolve complete staff names without assuming either name contains one word."""
        multi_word_surname = Account.objects.create_user(
            username="juliagdp",
            number=100000001,
            first_name="Julia",
            last_name="Gala de Pablo",
            email="julia.gala-de-pablo@leeds.ac.uk",
            is_staff=True,
        )
        multi_word_first_name = Account.objects.create_user(
            username="maryjane",
            number=100000002,
            first_name="Mary Jane",
            last_name="Watson",
            email="mary-jane.watson@leeds.ac.uk",
            is_staff=True,
        )
        widget = UserResource().fields["apt"].widget

        assert widget.clean("Julia Gala de Pablo") == multi_word_surname
        assert widget.clean("Mary Jane Watson") == multi_word_first_name

    def test_apt_widget_includes_superusers(self):
        """Allow a superuser account to be resolved as a student's APT."""
        superuser = Account.objects.create_user(
            username="administrator",
            number=100000001,
            first_name="Admin",
            last_name="User",
            email="admin.user@leeds.ac.uk",
            is_staff=False,
            is_superuser=True,
        )
        widget = UserResource().fields["apt"].widget

        for value in (superuser.initials, superuser.username, superuser.display_name, superuser.formal_name):
            with self.subTest(value=value):
                assert widget.clean(value) == superuser
        assert widget.clean(f"Unmatched Given Name {superuser.last_name.lower()}") == superuser

    def test_apt_widget_falls_back_to_unique_staff_surname(self):
        """Resolve the final word as a surname after full-name matching fails."""
        tutor = Account.objects.create_user(
            username="surname-tutor",
            number=100000001,
            first_name="Alex",
            last_name="Tutor",
            is_staff=True,
        )
        Account.objects.create_user(
            username="surname-student",
            number=200000001,
            first_name="Student",
            last_name="Tutor",
        )
        widget = UserResource().fields["apt"].widget

        assert widget.clean("Unmatched Given Names tutor") == tutor

    def test_apt_import_uses_year_when_student_was_level_one(self):
        """Derive the tutorial cohort from the current term and level of study."""
        year = Year.objects.create(name="Third Year", status="UG", level=3)
        tutor = Account.objects.create_user(
            username="tutor",
            number=100000001,
            first_name="Alex",
            last_name="Tutor",
            email="alex.tutor@leeds.ac.uk",
            is_staff=True,
        )
        dataset = Dataset(
            [
                "student",
                202000001,
                "Student",
                "One",
                "student@leeds.ac.uk",
                year.level,
                "202627",
                tutor.username,
            ],
            headers=["username", "number", "first_name", "last_name", "email", "year", "Term", "apt"],
        )

        UserResource().import_data(dataset, dry_run=False, raise_errors=True)

        assert TutorialAssignment.objects.get(student__username="student").tutorial.code == f"_{tutor.initials}_202425"

    def test_unresolved_apt_rejects_account_import_row(self):
        """Reject an account row when its non-empty APT cannot be resolved."""
        year = Year.objects.create(name="First Year", status="UG", level=1)
        dataset = Dataset(
            [
                "student",
                202000001,
                "Student",
                "One",
                "student@leeds.ac.uk",
                year.level,
                "202627",
                "unknown",
            ],
            headers=["username", "number", "first_name", "last_name", "email", "year", "Term", "apt"],
        )

        result = UserResource().import_data(dataset, dry_run=False, raise_errors=False)

        assert result.has_errors()
        assert "APT 'unknown' could not be resolved to a staff account" in str(result.row_errors()[0][1][0].error)
        assert not Account.objects.filter(username="student").exists()
        assert not TutorialAssignment.objects.exists()

    def test_empty_apt_allows_account_import_without_tutorial_assignment(self):
        """Allow an empty APT value without creating a tutorial assignment."""
        year = Year.objects.create(name="First Year", status="UG", level=1)
        dataset = Dataset(
            ["student", 202000001, "Student", "One", "student@leeds.ac.uk", year.level, "202627", ""],
            headers=["username", "number", "first_name", "last_name", "email", "year", "Term", "apt"],
        )

        result = UserResource().import_data(dataset, dry_run=False, raise_errors=True)

        assert not result.has_errors()
        assert Account.objects.filter(username="student").exists()
        assert not TutorialAssignment.objects.exists()
