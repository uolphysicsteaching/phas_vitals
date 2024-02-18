# -*- coding: utf-8 -*-
"""Import-Export Admin Resources for accounts"""

# Django imports
from django.contrib.auth.models import Group
from django.db.models import Q

# external imports
from import_export import fields, resources, widgets

# app imports
from .models import Account, Cohort, Programme


def _none(value):
    """Simple pass through."""
    return value


def _user_from_email(value):
    """Extract a username from an email address."""
    ret = value.split("@")[0].strip().lower()
    return ret


def _fname_from_name(value):
    """Return the first Word in the value."""
    words = [x for x in value.split(" ") if x != ""]
    return words[0].title()


def _lname_from_name(value):
    """Return the last Word in the value."""
    words = [x for x in value.split(" ") if x != ""]
    return words[-1].title()


class StrippedCharWidget(widgets.CharWidget):
    """Hacked to make sure usernames don't have leading or trailing space spaces."""

    def clean(self, value, row=None, *args, **kwargs):
        """Simply strips white space from the FKey before calling the parent."""
        return super().clean(value, row, *args, **kwargs).strip()


class ProgrammeWidget(widgets.ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        """Do a lookup attempting to match code or name."""
        qs = self.model.objects.filter(Q(code=value) | Q(name=value))
        if qs.count() < 1:
            return None
        return qs.last()


class AccountWidget(widgets.ForeignKeyWidget):
    """Try to match a user account."""

    def clean(self, value, row=None, *args, **kargs):
        """Attempt to match to a user account."""
        try:
            value = int(value)
            qs = self.model.objects.filter(number=value)
        except ValueError:
            qs = self.model.objects.filter(username=value)
        if qs.count() > 0:
            return qs.first()
        if "," in value:
            last_name, first_name = value.split(",")
            qs = self.model.objects.filter(last_name=last_name, first_name=first_name)
            if qs.count() > 0:
                return qs.first()
        elif " " in value:
            values = [x for x in value.split(" ") if x != ""]
            if values:
                first_name, last_name = values[0], values[-1]
                qs = self.model.objects.filter(last_name=last_name, first_name=first_name)
                if qs.count() > 0:
                    return qs.first()
        return None


class UserResource(resources.ModelResource):
    """Import Export resource class for Account objects."""

    groups = fields.Field(
        column_name="groups", attribute="groups", widget=widgets.ManyToManyWidget(Group, ";", "name")
    )

    programme = fields.Field(
        column_name="programme",
        attribute="programme",
        widget=ProgrammeWidget(Programme, "code"),
    )

    apt = fields.Field(
        column_name="apt",
        attribute="apt",
        widget=AccountWidget(Account, "display_name"),
    )

    username = fields.Field(column_name="username", attribute="username", widget=StrippedCharWidget())

    cohort = fields.Field(column_name="cohort", attribute="cohort", widget=widgets.ForeignKeyWidget(Cohort, "name"))

    class Meta:
        model = Account
        fields = (
            "username",
            "title",
            "first_name",
            "last_name",
            "email",
            "groups",
            "mark_count",
            "mark",
            "students",
            "is_staff",
            "number",
            "cohort",
            "programme",
            "registration_status",
            "apt",
        )
        import_id_fields = ["username"]

    field_mappings = {
        "username": {
            "username": _none,
            "Email Address": _user_from_email,
            "Email_Address": _user_from_email,
            "Email": _user_from_email,
        },
        "email": {"email": _none, "Email Address": _none, "Email_Address": _none, "Email": _none},
        "number": {"number": _none, "SID": _none, "Student_ID": _none, "Student ID": _none},
        "first_name": {
            "first_name": _none,
            "First_Name": _none,
            "First Name": _none,
            "Student_Name": _fname_from_name,
            "Student Name": _fname_from_name,
        },
        "last_name": {
            "last_name": _none,
            "Last_Name": _none,
            "Last Name": _none,
            "Student_Name": _lname_from_name,
            "Student Name": _lname_from_name,
        },
        "cohort": {"cohort": _none, "Term": _none, "Term_Code": _none},
        "programme": {"programme": _none, "Programme": _none},
        "registtration_status": {"registtration_status": _none, "Registration Status": _none, "ESTS_Code": _none},
        "apt": {"apt": _none, "tutor": _none, "Tutor Name": _none},
    }

    def import_row(self, row, instance_loader, using_transactions=True, dry_run=False, **kwargs):
        """Match up bad fields."""
        # sortout fields:
        for field, mappings in self.field_mappings.items():
            for col, func in mappings.items():
                if col in row:
                    row[field] = func(row[col])
                    break

        if ("Class" in row or "CRN" in row) and "groups" not in row:  # Setup a group
            row["groups"] = "Student"
        if "groups" in row and row["groups"] is not None and "Instructor" in row["groups"]:
            row["is_staff"] = 1
        for bad_field in ["mark_count", "mark", "students"]:  # remove calculated fields from import
            if bad_field in row:
                del row[bad_field]

        return super(UserResource, self).import_row(row, instance_loader, using_transactions, dry_run, **kwargs)


class GroupResource(resources.ModelResource):
    """Import Export Resource for Group objects."""

    class Meta:
        model = Group
        fields = ("name", "permissions")
        import_id_fields = ["name"]


class ProgrammeResource(resources.ModelResource):
    """Import Export Resource class for Programmes."""

    class Meta:
        model = Programme
        import_id_fields = ["code"]


class CohortResource(resources.ModelResource):
    """Import Export Resource classes for Cohort objects."""

    class Meta:
        model = Cohort
        fields = ("name",)
        import_id_fields = ["name"]
