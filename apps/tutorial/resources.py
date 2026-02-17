# -*- coding: utf-8 -*-
# Python imports
"""Import Export resources for tutorial app."""
# Python imports
import re

# external imports
from accounts.models import Account, Cohort
from accounts.resource import UsernameFKWidget
from import_export import fields, resources, widgets
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

    tutor = fields.Field(column_name="tutor", attribute="tutor", widget=UsernameFKWidget(Account, "username"))

    cohort = fields.Field(column_name="cohort", attribute="cohort", widget=widgets.ForeignKeyWidget(Cohort, "name"))

    class Meta:
        model = Tutorial
        fields = ("code", "tutor", "cohort", "notes")
        import_id_fields = ["code"]


class TutorialAssignmentResource(resources.ModelResource):
    """Tutorial Assignment resource class."""

    class Meta:
        model = TutorialAssignment
        fields = ("id", "tutorial", "student")
        import_id_fields = ["id"]

    tutorial = fields.Field(
        column_name="tutorial", attribute="tutorial", widget=widgets.ForeignKeyWidget(Tutorial, "code")
    )

    student = fields.Field(column_name="student", attribute="student", widget=UsernameFKWidget(Account, "username"))


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

    cohort = fields.Field(column_name="cohort", attribute="cohort", widget=widgets.ForeignKeyWidget(Cohort, "name"))


class AttendanceResource(resources.ModelResource):
    """Attendance Resource Class."""

    class Meta:
        model = Attendance
        fields = ("id", "student", "session", "score")

    student = fields.Field(column_name="student", attribute="student", widget=UsernameFKWidget(Account, "username"))
    session = fields.Field(column_name="session", attribute="session", widget=SessionFKWidget(Session, "name"))


class MeetingAttendanceResource(resources.ModelResource):
    """Meeting Attendance resource class."""

    class Meta:
        model = MeetingAttendance
        fields = ("id", "student", "meeting", "tutor", "submitted")

    student = fields.Field(column_name="student", attribute="student", widget=UsernameFKWidget(Account, "username"))
    meeting = fields.Field(column_name="meeting", attribute="meeting", widget=SessionFKWidget(Session, "name"))
    tutor = fields.Field(column_name="tutor", attribute="tutor", widget=UsernameFKWidget(Account, "username"))


class MeetingResource(resources.ModelResource):
    """Meeting Resource Class."""

    class Meta:
        model = Meeting
        fields = ("id", "name", "cohort", "notes", "due_date")
        import_id_fiekds = ("id",)

    cohort = fields.Field(column_name="cohort", attribute="cohort", widget=widgets.ForeignKeyWidget(Cohort, "name"))
