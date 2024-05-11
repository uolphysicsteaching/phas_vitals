# -*- coding: utf-8 -*-
# Python imports
"""Import Export resources for tutorial app."""
# Python imports
import re

# external imports
from accounts.models import Account, Cohort
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

    def render(self, value, obj=None):
        """Save the session as a sensible value."""
        if value is None:
            return ""
        return f"{value.cohort.name}-S{value.semester}-{value.name}"


class UsernameFKWidget(widgets.ForeignKeyWidget):
    """ "Foreign Key widget that allows a callback inside clean() method."""

    name_pat = re.compile(r"\((.*)\)")

    def __init__(self, *args, **kargs):
        """Add a hook for a function to process each element on import."""
        self.process = kargs.pop("process", self.name2username)
        super().__init__(*args, **kargs)

    def clean(self, value, row=None, *args, **kwargs):
        """Clean the value by trying to match each possible scheme."""
        value = self.process(value)
        return super().clean(value, row, *args, **kwargs)

    def name2username(self, name):
        """Try various ways to get a valid username.

        1) Look for some () and assume that contains a username
        2) Look for a comma and assume that that divides first name from last name
        3) Look for words and if more than 1 word, assume that it is first anem last name
        4) If only 1 word, assume it is a user id.
        """
        name = str(name)
        match = self.name_pat.search(name)
        if match:
            return match.group(1).lower()
        try:
            name = int(name)
            if name < 200000000:
                raise ValueError("numeric id < 2 billion not a student number")
            student = Account.objects.get(number=name)
            return student.username
        except ValueError:
            pass
        if "," in name:
            parts = name.split(",")
            firstname = parts[1].strip()
            surname = parts[0].strip()
        else:
            parts = [x for x in name.split(" ") if x != ""]
            if len(parts) < 2:
                return str.lower(name)
            if parts[0] in ["Mr", "Mrs", "Dr", "Prof", "Miss", "Ms"]:
                parts = parts[1:]
            firstname = parts[0]
            surname = parts[-1]
        possible = Account.objects.filter(first_name=firstname, last_name__contains=surname)
        if possible.count() == 1:
            return possible.all()[0].username
        else:
            return name

    def render(self, value, obj=None):
        """Save the user as display name."""
        if value is None:
            return ""
        return getattr(value, "display_name", "Oops!")


def name2username(name):
    """Try various ways to get a valid username.

    1) Look for some () and assume that contains a username
    2) Look for a comma and assume that that divides first name from last name
    3) Look for words and if more than 1 word, assume that it is first anem last name
    4) If only 1 word, assume it is a user id.
    """
    name_pat = re.compile(r"\((.*)\)")
    name = str(name)
    match = name_pat.search(name)
    if match:
        return match.group(1).lower()
    try:
        name = int(name)
        if name < 200000000:
            raise ValueError("numeric id < 2 billion not a student number")
        student = Account.objects.get(number=name)
        return student.username
    except ValueError:
        pass

    if "," in name:
        parts = name.split(",")
        firstname = parts[1].strip()
        surname = parts[0].strip()
    else:
        parts = [x for x in name.split(" ") if x != ""]
        if len(parts) < 2:
            return str.lower(name)
        if parts[0] in ["Mr", "Mrs", "Dr", "Prof", "Miss", "Ms"]:
            parts = parts[1:]
        firstname = parts[0]
        surname = parts[-1]
    possible = Account.objects.filter(first_name=firstname, last_name__contains=surname)
    if possible.count() == 1:
        return possible.all()[0].username
    else:
        return name


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
        fields = ("id", "tutorial", "studet")
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
