# -*- coding: utf-8 -*-
# Python imports
"""Import Export resources for tutorial app."""

# external imports
from accounts.models import Account, Cohort
from accounts.resource import AccountWidget, UsernameFKWidget
from import_export import fields, resources, widgets
from minerva.models import Module
from six import string_types

# app imports
from .models import (
    Attendance,
    Meeting,
    MeetingAttendance,
    Session,
    SessionType,
    Tutorial,
    TutorialAssignment,
)


class StrippedM2MWidget(widgets.ManyToManyWidget):
    """Hacked to make sure usernames don't have leading or trailing space spaces."""

    def __init__(self, *args, **kargs):
        """Add a hook for a function to process each element on import."""
        self.process = kargs.pop("process", lambda x: x)
        super(StrippedM2MWidget, self).__init__(*args, **kargs)

    def clean(self, value, row=None, *args, **kwargs):
        """Clean the data and split it into multiple values."""
        if isinstance(value, string_types):
            values = value.split(self.separator)
            values = [v.strip() for v in values]
            value = self.separator.join(values)
        return super().clean(value)


class SessionFKWidget(widgets.ForeignKeyWidget):
    """Identify Sessions as <year>-S<semester>-Name."""

    def __init__(self, *args, **kargs):
        """Add a hook for a function to process each element on import."""
        self.process = kargs.pop("process", self.label2session)
        super().__init__(*args, **kargs)

    def label2session(self, label):
        """Copvert name to a session id."""
        try:
            cohort, semester, name = label.split("-")
            cohort = cohort.replace("/", "")
            semester = int(semester[1])
            session = Session.objects.get(cohort=cohort, semester=semester, name=name)
        except Exception:
            return label
        return session.pk

    def clean(self, value, row=None, *args, **kwargs):
        """Clean the session foreign key."""
        value = self.process(value)
        return super().clean(value, row, *args, **kwargs)

    def render(self, value, obj=None, **kwargs):
        """Save the session as a sensible value."""
        if value is None:
            return ""
        return f"{value.cohort.name}-S{value.semester}-{value.name}"


class TutorialsResource(resources.ModelResource):
    """Resource class for Tutorial Groups."""

    tutor = fields.Field(
        column_name="tutor",
        attribute="tutor",
        widget=UsernameFKWidget(Account, "username"),
    )

    cohort = fields.Field(
        column_name="cohort",
        attribute="cohort",
        widget=widgets.ForeignKeyWidget(Cohort, "name"),
    )

    class Meta:
        model = Tutorial
        fields = ("code", "tutor", "cohort", "notes")
        import_id_fields = ["code"]


class TutorialAssignmentResource(resources.ModelResource):
    """Tutorial Assignment resource class."""

    tutor_widget = AccountWidget(Account, "display_name", staff_only=True, exclude_superusers=True)

    class Meta:
        model = TutorialAssignment
        fields = ("id", "tutorial", "student")
        import_id_fields = ["id"]

    tutorial = fields.Field(
        column_name="tutorial",
        attribute="tutorial",
        widget=widgets.ForeignKeyWidget(Tutorial, "code"),
    )

    student = fields.Field(
        column_name="student",
        attribute="student",
        widget=UsernameFKWidget(Account, "username"),
    )

    def before_import(self, dataset, **kwargs):
        """Add the canonical direct-mapping fields required during row preparation."""
        for field_name in (*self._meta.import_id_fields, "tutorial", "student"):
            if field_name not in dataset.headers:
                dataset.headers.append(field_name)
        super().before_import(dataset, **kwargs)

    def before_import_row(self, row, **kwargs):
        """Resolve adaptive student and tutorial fields before importing a row."""
        super().before_import_row(row, **kwargs)
        student = self._resolve_student(row)
        row["student"] = student.username

        existing_assignment = (
            TutorialAssignment.objects.filter(student=student).select_related("tutorial__cohort").first()
        )
        assignment_id = self._row_value(row, "id")
        if assignment_id:
            row["id"] = assignment_id
        elif existing_assignment is not None:
            row["id"] = existing_assignment.pk

        tutorial_value = self._row_value(row, "tutorial")
        if tutorial_value:
            row["tutorial"] = tutorial_value
            tutorial = self.fields["tutorial"].widget.clean(tutorial_value, row=row)
        else:
            cohort = self._resolve_cohort(student, existing_assignment)
            tutor = self._resolve_tutor(self._row_value(row, "Tutor"), row)
            tutorial_code = f"_{tutor.initials}_{cohort.pk}"
            try:
                tutorial = Tutorial.objects.get(code=tutorial_code)
            except Tutorial.DoesNotExist as error:
                raise ValueError(f"Tutorial group '{tutorial_code}' does not exist.") from error
            except Tutorial.MultipleObjectsReturned as error:
                raise ValueError(f"Multiple tutorial groups match code '{tutorial_code}'.") from error
        row["tutorial"] = tutorial.code
        row["_replace_assignment"] = existing_assignment is not None and existing_assignment.tutorial_id != tutorial.pk

    def before_save_instance(self, instance, row, **kwargs):
        """Remove a changed assignment immediately before saving its replacement."""
        super().before_save_instance(instance, row, **kwargs)
        should_write = not kwargs.get("dry_run", False) or kwargs.get("using_transactions", False)
        if row.get("_replace_assignment") and should_write:
            instance.delete()

    def _resolve_student(self, row):
        """Resolve the student using direct mapping, student number, or their name."""
        direct_value = self._row_value(row, "student")
        if direct_value:
            return self.fields["student"].widget.clean(direct_value, row=row)

        student_number = self._row_value(row, "Student ID")
        if student_number:
            student_number = self._spreadsheet_text(student_number)
            try:
                return Account.objects.get(number=student_number)
            except Account.DoesNotExist as error:
                raise ValueError(f"No student account has Student ID '{student_number}'.") from error
            except Account.MultipleObjectsReturned as error:
                raise ValueError(f"Multiple student accounts have Student ID '{student_number}'.") from error

        last_name = self._row_value(row, "last_name", "Surname")
        first_name = self._row_value(row, "first_name", "First Name")
        if not last_name or not first_name:
            raise ValueError("A student, Student ID, or last_name and first_name pair is required.")
        try:
            return Account.objects.get(
                last_name__iexact=self._spreadsheet_text(last_name),
                first_name__iexact=self._spreadsheet_text(first_name),
            )
        except Account.DoesNotExist as error:
            raise ValueError(f"No student account matches '{last_name}, {first_name}'.") from error
        except Account.MultipleObjectsReturned as error:
            raise ValueError(f"Multiple student accounts match '{last_name}, {first_name}'.") from error

    @staticmethod
    def _resolve_cohort(student, existing_assignment):
        """Resolve the cohort from an existing assignment or the student's first enrolment."""
        if existing_assignment is not None:
            cohort = existing_assignment.tutorial.cohort
            if cohort is None:
                raise ValueError("The student's existing tutorial group has no cohort.")
            return cohort

        enrolment = student.module_enrollments.select_related("module__year").order_by("pk").first()
        if enrolment is None:
            raise ValueError("The student has no module enrolment from which to determine a cohort.")
        return enrolment.module.year

    def _resolve_tutor(self, value, row):
        """Resolve a tutor using the shared APT account matcher."""
        value = self._spreadsheet_text(value)
        if not value:
            raise ValueError("A Tutor value is required when tutorial is not supplied.")

        tutor = self.tutor_widget.clean(value, row=row)
        if tutor is None:
            raise ValueError(f"Tutor '{value}' could not be resolved to a non-superuser staff account.")
        return tutor

    @classmethod
    def _row_value(cls, row, *column_names):
        """Return the first non-empty value from case-insensitive column names."""
        for column_name in column_names:
            normalised_name = column_name.strip().casefold()
            for key, value in row.items():
                if str(key).strip().casefold() == normalised_name and cls._spreadsheet_text(value):
                    return value
        return None

    @staticmethod
    def _spreadsheet_text(value):
        """Normalise identifiers read from spreadsheet number cells."""
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()


class SessionTypeResource(resources.ModelResource):
    """Session Type Resource Class."""

    class Meta:
        model = SessionType
        fields = ("id", "name", "description")
        import_id_fiekds = ("id",)


class SessionResource(resources.ModelResource):
    """Session Resource class."""

    class Meta:
        model = Session
        fields = ("id", "cohort", "semester", "name", "start", "end")
        import_id_fiekds = ("id",)

    cohort = fields.Field(
        column_name="cohort",
        attribute="cohort",
        widget=widgets.ForeignKeyWidget(Cohort, "name"),
    )


class AttendanceResource(resources.ModelResource):
    """Attendance Resource Class."""

    class Meta:
        model = Attendance
        fields = ("id", "student", "session", "score")

    student = fields.Field(
        column_name="student",
        attribute="student",
        widget=UsernameFKWidget(Account, "username"),
    )
    session = fields.Field(
        column_name="session",
        attribute="session",
        widget=SessionFKWidget(Session, "name"),
    )


class MeetingAttendanceResource(resources.ModelResource):
    """Meeting Attendance resource class."""

    class Meta:
        model = MeetingAttendance
        fields = (
            "id",
            "student",
            "meeting",
            "staff",
            "status",
            "flag",
            "created_at",
            "updated_at",
        )

    student = fields.Field(
        column_name="student",
        attribute="student",
        widget=UsernameFKWidget(Account, "username"),
    )
    meeting = fields.Field(
        column_name="meeting",
        attribute="meeting",
        widget=widgets.ForeignKeyWidget(Meeting, "id"),
    )
    staff = fields.Field(
        column_name="staff",
        attribute="staff",
        widget=UsernameFKWidget(Account, "username"),
    )


class MeetingResource(resources.ModelResource):
    """Meeting Resource Class."""

    class Meta:
        model = Meeting
        fields = ("id", "name", "module", "notes", "due_semester", "due_week")
        import_id_fields = ("id",)

    module = fields.Field(
        column_name="module",
        attribute="module",
        widget=widgets.ForeignKeyWidget(Module, "id"),
    )
