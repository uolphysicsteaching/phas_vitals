# -*- coding: utf-8 -*-
"""Import-Export Admin Resources for accounts"""

# Django imports
from django.contrib.auth.models import Group
from django.db.models import Q

# external imports
from import_export import fields, resources, widgets

# app imports
from .models import Account, Cohort, Programme


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

    tutor = fields.Field(
        column_name="tutor",
        attribute="tutor",
        widget=widgets.ForeignKeyWidget(Account, "display_name"),
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
            "tutor",
        )
        import_id_fields = ["username"]

    def import_row(self, row, instance_loader, using_transactions=True, dry_run=False, **kwargs):
        """Match up bad fields."""
        if "username" not in row and "Email Address" in row:  # Create username and email columns
            parts = row["Email Address"].split("@")
            row["username"] = parts[0].strip().lower()
            row["email"] = row["Email Address"].strip()
        if "username" not in row and "Email_Address" in row:  # Create username and email columns
            parts = row["Email_Address"].split("@")
            row["username"] = parts[0].strip().lower()
            row["email"] = row["Email_Address"].strip()
        if "first_name" not in row and "last_name" not in row and "Student Name" in row:  # Sort out name
            parts = row["Student Name"].split(", ")
            row["last_name"] = parts[0].strip()
            row["first_name"] = parts[1].strip()
        elif "First_Name" in row and "Last_Name" in row:
            row["first_name"] = row["First_Name"]
            row["last_name"] = row["Last_Name"]
        if "Student ID" in row and "number" not in row:  # Student ID number
            row["number"] = row["Student ID"]
        elif "Student_ID" in row and "number" not in row:  # Student ID number
            row["number"] = row["Student_ID"]
        if ("Class" in row or "CRN" in row) and "groups" not in row:  # Setup a group
            row["groups"] = "Student"
        if "groups" in row and row["groups"] is not None and "Instructor" in row["groups"]:
            row["is_staff"] = 1
        if "Term" in row and "cohort" not in row:
            row["cohort"] = row["Term"]
        elif "Term_Code" in row and "cohort" not in row:
            row["cohort"] = row["Term_Code"]
        if "Programme" in row and "programme" not in row:
            row["programme"] = row["Programme"]
        if "Registration Status" in row and "registtration_status" not in row:
            row["registration_status"] = row["Registration Status"]
        elif "ESTS_Code" in row and "registtration_status" not in row:
            row["registration_status"] = row["ESTS_Code"]
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
