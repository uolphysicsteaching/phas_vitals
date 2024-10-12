"""Admin interfaces classes for the accounts app."""

# Python imports
import csv
from io import StringIO

# Django imports
from django.contrib.admin import (
    SimpleListFilter,
    action,
    display,
    register,
    site,
    sites,
)
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from django.db.models import Case, F, When
from django.http import StreamingHttpResponse
from django.utils.translation import gettext_lazy as _

# external imports
from import_export.admin import ImportExportMixin, ImportExportModelAdmin

# app imports
from .forms import UserAdminForm
from .models import Account, AccountGroup, Cohort, Programme, Section
from .resource import (
    CohortResource,
    GroupResource,
    ProgrammeResource,
    SectionResource,
    UserResource,
)


class StudentListFilter(SimpleListFilter):
    """A filter for selecting student accounts sorted by surname."""

    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = "Student"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "student"

    def lookups(self, request, model_admin):
        """Return a sorted list of student names."""
        res = Account.students.filter(groups__name="Student").order_by("last_name", "first_name")
        return tuple([(user.username, user.display_name) for user in res.all()])

    def queryset(self, request, queryset):
        """Return the object with a student of the right username."""
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        fields = [f.name for f in queryset.model._meta.get_fields()]
        if self.value() is None:
            return queryset
        if "user" in fields:
            return queryset.filter(user__username=self.value())
        elif "student" in fields:
            return queryset.filter(student__username=self.value())


class CohortListFilter(SimpleListFilter):
    """A filter for selecting student accounts sorted by surname."""

    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = "Cohort"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "cohort"

    def lookups(self, request, model_admin):
        """Return a sorted list of student names."""
        return tuple([(cohort.name, str(cohort)) for cohort in Cohort.objects.all()])

    def queryset(self, request, queryset):
        """Return the object with a cohort if the right name."""
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        fields = [f.name for f in queryset.model._meta.get_fields()]
        if self.value() is None:
            return queryset
        if "modules" in fields:
            return queryset.annotate(year=F("modules__year__name")).filter(year=self.value()).distinct()
        return queryset


site.unregister(Group)

# Register your models here.


@register(Programme)
class ProgrammeAdmin(ImportExportModelAdmin):
    """Admin interface for Programme Objects."""

    list_display = ("name", "code")
    list_filter = list_display
    search_fields = list_filter

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return ProgrammeResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return ProgrammeResource


@register(Cohort)
class CohortAdmin(ImportExportModelAdmin):
    """Minimal Cohort Admin Interface."""

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return CohortResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return CohortResource


@register(Section)
class SectionAdmin(ImportExportModelAdmin):
    """Minimal Cohort Admin Interface."""

    list_display = ["name", "group_code", "group_set", "self_enrol"]
    search_fields = ["name", "group_code", "group_set", "description"]
    actions = ["export_groups"]

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return SectionResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return SectionResource

    @action(description="Export Minerva Groups")
    def export_groups(self, request, queryset):
        """Action to export a Minerva groups csv file."""

        def rows(queryset):
            csvfile = StringIO()
            csvwriter = csv.writer(csvfile)

            def read_and_flush():
                csvfile.seek(0)
                data = csvfile.read()
                csvfile.seek(0)
                csvfile.truncate()
                return data

            queryset = queryset.annotate(
                enrol_ok=Case(When(self_enrol=True, then="Y"), When(self_enrol=False, then="N"))
            )
            csvwriter.writerow(["Group Code", "Title", "Description", "Group Set", "Self Enroll"])
            yield read_and_flush()

            for row in queryset.all():
                csvwriter.writerow(
                    [getattr(row, attr, "") for attr in ["group_code", "name", "description", "group_set", "enrol_ok"]]
                )
                yield read_and_flush()

        response = StreamingHttpResponse(rows(queryset), content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename='Minerva {self.model.__name__}s.csv'"

        return response


try:
    site.unregister(Account)
except sites.NotRegistered:
    pass


@register(Account)
class AccountAdmin(ImportExportMixin, UserAdmin):
    """Sectioned Admin interface for Account Objects."""  # TODO: Add Tabs if Baton allows it

    form = UserAdminForm

    fieldsets = (
        (
            _("Personal info"),
            {
                "fields": [
                    ("username", "number"),
                    ("title", "first_name", "givenName", "last_name"),
                    ("email"),
                    ("programme", "registration_status", "section"),
                ],
                "classes": [
                    "order-0",
                    "baton-tabs-init",
                    "baton-tab-inline-attribute",
                    "baton-tab-fs-permissions",
                    "baton-tab-fs-dates",
                ],
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (("is_active", "is_staff", "is_superuser"), "groups", "user_permissions"),
                "classes": ("tab-fs-permissions",),
            },
        ),
        (
            _("Important dates"),
            {
                "fields": (("last_login", "date_joined"),),
                "classes": ("tab-fs-dates",),
            },
        ),
    )
    list_per_page = 250
    list_display = [
        "username",
        "first_name",
        "givenName",
        "last_name",
        "number",
        "programme",
        "is_staff",
        "is_superuser",
        "section",
    ]
    list_editable = ["number", "programme", "is_staff", "is_superuser"]
    list_filter = ("groups", CohortListFilter, "programme", "is_staff", "is_superuser", "section")
    search_fields = (
        "username",
        "first_name",
        "givenName",
        "last_name",
        "groups__name",
        "programme__name",
        "section__name",
    )
    actions = ["export_roster", "export_groups"]

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return UserResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return UserResource

    @action(description="Export Gradescope roster")
    def export_roster(self, request, queryset):
        """Action to export Gradescope Roster file."""

        def rows(queryset):
            csvfile = StringIO()
            csvwriter = csv.writer(csvfile)

            def read_and_flush():
                csvfile.seek(0)
                data = csvfile.read()
                csvfile.seek(0)
                csvfile.truncate()
                return data

            csvwriter.writerow(["First Name", "Last Name", "SID", "Email", "Role", "Section"])
            yield read_and_flush()

            queryset = queryset.annotate(group=F("groups__name"), sect=F("section__name"))
            for row in queryset.all():
                csvwriter.writerow(
                    [
                        getattr(row, attr, "")
                        for attr in ["first_name", "last_name", "number", "email", "group", "sect"]
                    ]
                )
                yield read_and_flush()

        response = StreamingHttpResponse(rows(queryset), content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename={self.model.__name__} Roster.csv"

        return response

    @action(description="Export Minerva Groups")
    def export_groups(self, request, queryset):
        """Action to export a Minerva groups csv file."""

        def rows(queryset):
            csvfile = StringIO()
            csvwriter = csv.writer(csvfile)

            def read_and_flush():
                csvfile.seek(0)
                data = csvfile.read()
                csvfile.seek(0)
                csvfile.truncate()
                return data

            csvwriter.writerow(["Group Code", "User Name", "Student Id", "First Name", "Last Name", "Group Set"])
            yield read_and_flush()

            queryset = queryset.annotate(group=F("section__group_code"), set=F("section__group_set"))
            for row in queryset.all():
                csvwriter.writerow(
                    [
                        getattr(row, attr, "")
                        for attr in ["group", "username", "number", "first_name", "last_name", "set"]
                    ]
                )
                yield read_and_flush()

        response = StreamingHttpResponse(rows(queryset), content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename={self.model.__name__} Groups.csv"

        return response


@register(AccountGroup)
class ImportExportGroupAdmin(ImportExportMixin, GroupAdmin):
    """Rather Minimal Group Admin interface."""

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return GroupResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return GroupResource
