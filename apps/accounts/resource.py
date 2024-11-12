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
    given_name_pattern = re.compile(r"(?P<last_name>[^\,]+)\,(?P<givenName>[^\(]+)\((?P<first_name>[^)]+)\)")

    def clean(self, value, row=None, *args, **kwargs):
        """Attempt to match to a user account."""
        if not value:
            return None

        # Try matching by number or username
        account = self._match_by_number_or_username(value)
        if account:
            return account

        # Build initials and formal names lookup
        initials, formal_names = self._build_initials_and_formal_names()

        # Try matching by initials or formal names
        account = self._match_by_initials_or_formal_names(value, initials, formal_names)
        if account:
            return account

        # Try matching by display name or given name
        account = self._match_by_name_pattern(value)
        if account:
            return account

        # Try matching by first and last name
        return self._match_by_first_last_name(value)

    def _match_by_number_or_username(self, value):
        """See if value can be interpreted as a SID or usnername."""
        try:
            value = int(value)
            qs = Account.objects.filter(number=value)
        except (TypeError, ValueError):
            qs = Account.objects.filter(username=value)
        return qs.first() if qs.exists() else None

    def _build_initials_and_formal_names(self):
        """Builtables of staff initials and formal names."""
        initials = {}
        formal_names = {}
        for staff in Account.objects.filter(is_staff=True):
            initials[staff.initials] = staff
            formal_names[staff.formal_name] = staff
        return initials, formal_names

    def _match_by_initials_or_formal_names(self, value, initials, formal_names):
        """Lookup tables of initials or formal names for a match."""
        return initials.get(value) or formal_names.get(value)

    def _match_by_name_pattern(self, value):
        """Match user by given name regexp."""
        pattern = self.given_name_pattern if "(" in value else self.display_name_pattern
        match = pattern.match(value)
        if match:
            qs = Account.objects.filter(**match.groupdict())
            return qs.first() if qs.exists() else None
        return None

    def _match_by_first_last_name(self, value):
        """Match by first and las names."""
        if " " in value:
            first_name, last_name = value.split(" ")[0], value.split(" ")[-1]
            qs = Account.objects.filter(first_name=first_name, last_name=last_name)
            return qs.first() if qs.exists() else None
        return None


class AccountsWidget(widgets.ManyToManyWidget):
    """An import-export widget that understands lists of user names."""

    def clean(self, value, row=None, **kwargs):
        """Perform lookups to match lists of user names or IDs."""
        if not value:
            return Account.objects.none()

        ids = self._parse_ids(value)
        accounts = self._get_accounts_by_number(ids) or self._get_accounts_by_username(ids)

        if accounts.exists():
            return accounts
        return self._get_accounts_by_name(ids)

    def _parse_ids(self, value):
        """Parse and clean the input value into a list of IDs."""
        if isinstance(value, (float, int)):
            return [int(value)]
        return filter(None, [i.strip() for i in value.split(self.separator)])

    def _get_accounts_by_number(self, ids):
        """Attempt to retrieve accounts by student number."""
        try:
            return Account.objects.filter(number__in=[int(i) for i in ids])
        except (TypeError, ValueError):
            return None

    def _get_accounts_by_username(self, ids):
        """Attempt to retrieve accounts by username."""
        return Account.objects.filter(username__in=ids)

    def _get_accounts_by_name(self, ids):
        """Retrieve accounts by parsing names."""
        pks = self._match_names_to_pks(ids)
        return Account.objects.filter(pk__in=pks)

    def _match_names_to_pks(self, ids):
        """Match names to primary keys."""
        pks = []
        initials, formal_names = self._build_name_lookup()

        for value in ids:
            if "," in value:  # last_name, first_name
                pks.extend(self._match_last_first_name(value))
            elif value in initials:  # Staff member initials
                pks.append(initials[value])
            elif value in formal_names:  # Staff member formal names
                pks.append(formal_names[value])
            else:  # first_name initials last_name
                pks.extend(self._match_first_last_name(value))
        return pks

    def _build_name_lookup(self):
        """Build lookup dictionaries for initials and formal names."""
        initials = {}
        formal_names = {}
        for staff in Account.objects.filter(is_staff=True):
            initials[staff.initials] = staff.pk
            formal_names[staff.formal_name] = staff.pk
        return initials, formal_names

    def _match_last_first_name(self, value):
        """Match accounts by last name, first name."""
        last_name, first_name = value.split(",")
        return Account.objects.filter(last_name=last_name.strip(), first_name=first_name.strip()).values_list(
            "pk", flat=True
        )

    def _match_first_last_name(self, value):
        """Match accounts by first name, last name."""
        values = [x for x in value.split(" ") if x]
        if values:
            first_name, last_name = values[0], values[-1]
            return Account.objects.filter(last_name=last_name, first_name=first_name).values_list("pk", flat=True)
        return []


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
