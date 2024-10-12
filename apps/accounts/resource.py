# -*- coding: utf-8 -*-
"""Import-Export Admin Resources for accounts"""

# Python imports
import re

# Django imports
from django.contrib.auth.models import Group
from django.db.models import Q

# external imports
from import_export import fields, resources, widgets

# app imports
from .models import Account, Cohort, Programme, Section


def _none(value):
    """Simple pass through."""
    return value


def _user_from_email(value):
    """Extract a username from an email address."""
    ret = value.split("@")[0].strip().lower()
    return ret


def _fname_from_name(value):
    """Return the first Word in the value."""
    if "," in value:  # Assume last_name, name (initial)
        words = [x.strip() for x in value.split(",")]
        first_names = [x.strip() for x in words[1].split(" ")]
        return first_names[0].title()
    else:
        words = [x for x in value.split(" ") if x != ""]
    return words[0].title()


def _lname_from_name(value):
    """Return the last Word in the value."""
    if "," in value:  # Assume last_name, name (initial)
        words = [x.strip() for x in value.split(",")]
        return words[0].title()
    else:
        words = [x for x in value.split(" ") if x != ""]
    return words[-1].title()


class StrippedCharWidget(widgets.CharWidget):
    """Hacked to make sure usernames don't have leading or trailing space spaces."""

    def clean(self, value, row=None, *args, **kwargs):
        """Simply strips white space from the FKey before calling the parent."""
        return super().clean(value, row, *args, **kwargs).strip()


class ProgrammeWidget(widgets.ForeignKeyWidget):
    """Import export ediget that looks up programmes by name or code."""

    def clean(self, value, row=None, *args, **kwargs):
        """Do a lookup attempting to match code or name."""
        qs = Programme.objects.filter(Q(code=value) | Q(name=value))
        if qs.count() < 1:
            return None
        return qs.last()


class ProgrammesWidget(widgets.ManyToManyWidget):
    """Import Export Wdiget that understands lists of programmes"""

    def clean(self, value, row=None, **kwargs):
        """Do a lookup attempting to match code or name."""
        if not value:
            return Programme.objects.none()
        if isinstance(value, (float, int)):
            ids = [int(value)]
        else:
            ids = value.split(self.separator)
            ids = filter(None, [i.strip() for i in ids])

        qs = Programme.objects.filter(Q(code__in=ids) | Q(name__in=ids))
        if qs.count() < 1:
            return None
        return qs.all()


class AccountWidget(widgets.ForeignKeyWidget):
    """Try to match a user account."""

    display_name_pattern = re.compile(r"(?P<last_name>[^\,]+)\,(?P<first_name>[^\(]+)$")
    given_name__pattern = re.compile(r"(?P<last_name>[^\,]+)\,(?P<givenName>[^\(]+)\((?P<first_name>]^\)]+)\)")

    def clean(self, value, row=None, *args, **kargs):
        """Attempt to match to a user account."""
        if value is None:
            return None
        try:
            value = int(value)
            qs = Account.objects.filter(number=value)
        except (TypeError, ValueError):
            qs = Account.objects.filter(username=value)
        if qs.count() > 0:
            return qs.first()

        initials = {}
        formal_names = {}
        for staff in Account.objects.filter(is_staff=True):
            initials[staff.initials] = staff
            formal_names[staff.formal_name] = staff

        try:
            return initials[value]
        except KeyError:
            pass
        try:
            return formal_names[value]
        except KeyError:
            pass

        if "," in value:
            if "(" in value:
                pattern = self.given_name__pattern
            else:
                pattern = self.display_name_pattern
            if match := pattern.match(value):
                qs = Account.objects.filter(**match.groupdict())
                if qs.count() > 0:
                    return qs.first()

        elif " " in value:
            values = [x for x in value.split(" ") if x != ""]
            if values:
                first_name, last_name = values[0], values[-1]
                qs = Account.objects.filter(last_name=last_name, first_name=first_name)
                if qs.count() > 0:
                    return qs.first()
        return None


class AccountsWidget(widgets.ManyToManyWidget):
    """An import-export widget that understands lists of user names."""

    def clean(self, value, row=None, **kwargs):
        """Do a lookup attempting to match code or name."""
        if not value:  # Early exit
            return Account.objects.none()
        if isinstance(value, (float, int)):  # Single int/float id
            ids = [int(value)]
        else:  # Assume a string that we can split on separator
            ids = value.split(self.separator)
            ids = filter(None, [i.strip() for i in ids])

        try:  # try as a list of student numbers
            qs = Account.objects.filter(number__in=[int(i) for i in ids])
        except (TypeError, ValueError):  # not a list of numbers, try as a list of usernames
            qs = Account.objects.filter(username__in=ids)
        if qs.count() > 0:
            return qs.all()
        # At this point we are going to have to mangle for a name
        # First build tables of initials and formal names
        pks = []
        initials = {}
        formal_names = {}
        for staff in Account.objects.filter(is_staff=True):
            initials[staff.initials] = staff.pk
            formal_names[staff.formal_name] = staff.pk

        for value in ids:  # recast from display name
            if "," in value:  # last_name, first_name
                last_name, first_name = value.split(",")
                qs = Account.objects.filter(last_name=last_name, first_name=first_name)
                if qs.count() > 0:
                    pks.append(qs.first().pk)

            elif value in initials:  # Staff member initials
                pks.append(initials[value])

            elif value in formal_names:  # Staff member formal names
                pks.append(formal_names[value])

            elif " " in value:  # first_name initials last_name
                values = [x for x in value.split(" ") if x != ""]
                if values:
                    first_name, last_name = values[0], values[-1]
                    qs = Account.objects.filter(last_name=last_name, first_name=first_name)
                    if qs.count() > 0:
                        pks.append(qs.first().pk)
        # pks is a list of matching primary keys, need to lookup again to get correct queryset
        qs = Account.objects.filter(pk__in=pks)
        if qs.count() > 0:
            return qs.all()
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
    section = fields.Field(
        column_name="section", attribute="section", widget=widgets.ForeignKeyWidget(Section, "name")
    )

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
            "is_superuser",
            "number",
            "programme",
            "section",
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
        "programme": {"programme": _none, "Programme": _none},
        "section": {"section": _none, "Section": _none},
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


class SectionResource(resources.ModelResource):
    """Import Export Resource classes for Cohort objects."""

    class Meta:
        model = Section
        fields = ("name", "group_code", "group_set")
        import_id_fields = ["name"]
