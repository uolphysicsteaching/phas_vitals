# Django imports
from django import forms
from django.contrib.admin import SimpleListFilter, register, site, sites
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

# external imports
from import_export.admin import ImportExportMixin, ImportExportModelAdmin

# app imports
from .models import Account, Cohort, Programme
from .resource import (
    CohortResource,
    GroupResource,
    ProgrammeResource,
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
        res = Account.objects.filter(groups__name="Student").order_by("last_name", "first_name")
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


site.unregister(Group)

# Register your models here.


class UserAdminForm(forms.ModelForm):
    """Tweaks to the User Admin account form."""

    class Meta:
        model = Account
        widgets = {
            "first_name": forms.TextInput(attrs={"size": 10}),
            "last_name": forms.TextInput(attrs={"size": 10}),
        }
        exclude = ()


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
                    ("username", "number", "cohort"),
                    ("title", "first_name", "last_name"),
                    ("email"),
                    ("programme", "registration_status"),
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
    list_display = ["username", "last_name", "first_name", "cohort", "programme", "is_staff", "is_superuser"]
    list_editable = ["cohort", "programme", "is_staff", "is_superuser"]
    list_filter = ("groups", "cohort", "programme", "is_staff", "is_superuser")
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "groups__name",
        "cohort__name",
        "programme__name",
    )

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return UserResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return UserResource


@register(Group)
class ImportExportGroupAdmin(ImportExportMixin, GroupAdmin):
    """Rather Minimal Group Admin interface."""

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return GroupResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return GroupResource
