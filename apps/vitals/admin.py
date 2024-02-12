# Django imports
from django.contrib import admin

# external imports
from import_export.admin import ImportExportMixin, ImportExportModelAdmin
from util.admin import add_action, add_inlines
from accounts.models import Account

# app imports
from .models import VITAL, VITAL_Result, VITAL_Test_Map
from .resource import (
    VITAL_ResultResource, VITAL_Test_MapResource, VITALResource,
)

# Register your models here.


class VITAL_Test_MapInline(admin.StackedInline):

    """Inline Admin for Test Mapping for use with VITALs."""

    model = VITAL_Test_Map
    extra = 0


class VITAL_ResultInline(admin.StackedInline):

    """Inline admin for Test Result mapping for VITALS."""

    model = VITAL_Result
    extra = 0


class VITALInline(admin.StackedInline):

    """Inline admin for VITALS."""

    model = VITAL
    extra = 0



add_inlines("accounts.Account", VITAL_ResultInline, "vital_results")
add_inlines("minerva.Test", VITAL_Test_MapInline, "vitals_mappings")
add_inlines("minerva.Module", VITALInline, "VITALS")


@admin.action(description="Force Update of VITALs")
def update_user_vitals(modelAdmin, request, queryset):
    """Force an update of all VITALs for the selected users."""
    for vr in VITAL_Result.objects.filter(user__in=queryset.all()):
        vr.vital.check_vital(vr.user)


@admin.action(description="Force Update of VITALs")
def update_module_vitals(modelAdmin, request, queryset):
    """Force an update of all VITALs for the selected users."""
    vrs=VITAL_Result.objects.filter(user__module_enrollments__module__in=queryset.all())
    for vr in VITAL_Result.objects.filter(user__modules__in=queryset.all()):
        vr.vital.check_vital(vr.user)

@admin.action(description="Force Update of VITAL")
def update_vital_users(modelAdmin, request, queryset):
    """Force an update of all users for the selected VITALs."""
    users = Account.objects.filter(modules__VITALS__in=queryset.all())
    for user in users:
        for vital in queryset.all():
            vital.check_vital(user)

add_action("accounts.Account", update_user_vitals)
add_action("minerva.Module", update_module_vitals)


@admin.register(VITAL)
class VITALAdmin(ImportExportModelAdmin):

    """Admin class for VITALs."""

    list_display = ("name", "module")
    list_filter = list_display
    search_fields = ["name", "description", "module__name"]
    inlines = [VITAL_Test_MapInline, VITAL_ResultInline]
    actions = [update_vital_users,]

    fieldsets = (
        (
            "Details",
            {
                "fields": ("name", "description", "module"),
                "classes": ("baton-tabs-init", "baton-tab-inline-tests_mappings", "baton-tab-inline-student_results"),
            },
        ),
    )

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return VITALResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return VITALResource


@admin.register(VITAL_Test_Map)
class VITAL_Test_MapAdmin(ImportExportModelAdmin):

    """Admin Interface for Mappings between Tests and VITALs."""

    list_display = ("test", "vital", "necessary", "sufficient")
    list_filter = list_display
    search_fields = ["test__name", "vital__name", "vital__module__name", "test__module__name"]

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return VITAL_Test_MapResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return VITAL_Test_MapResource


@admin.register(VITAL_Result)
class VITAL_ResultAdmin(ImportExportModelAdmin):

    """Admin interface for VITAL Results."""

    list_display = ("vital", "user", "date_passed")
    list_filter = list_display
    search_fields = ["vital__name", "user__first_name", "user__last_name", "user__username", "vital__module__name"]

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return VITAL_ResultResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return VITAL_ResultResource
