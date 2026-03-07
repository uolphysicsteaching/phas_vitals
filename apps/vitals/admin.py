# Python imports
import logging

# Django imports
from django.contrib import admin, messages

# external imports
from accounts.admin import StudentListFilter
from accounts.models import Account
from import_export.admin import ImportExportModelAdmin
from minerva.admin import ModuleListFilter
from util.admin import add_action, add_inlines

# app imports
from phas_vitals import celery_app

# app imports
from .forms import VITAL_ResultForm, VITAL_Test_MapForm, VITALForm
from .models import VITAL, VITAL_Result, VITAL_Test_Map
from .resource import (
    VITAL_ResultResource,
    VITAL_Test_MapResource,
    VITALResource,
)

logger = logging.getLogger("celery_tasks")


class VITALListFilter(admin.SimpleListFilter):
    """A filter for selecting student accounts sorted by surname."""

    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = "VITAL"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "VITAL"

    def lookups(self, request, model_admin):
        """Return a sorted list of VITAL options.

        Returns:
            (tuple): A tuple of (VITAL_ID, display_string) tuples for VITAL options.
        """
        vital_data = VITAL.objects.all().order_by("VITAL_ID").values_list("VITAL_ID", "name")
        return tuple([(vid, f"{vid} - {name}") for vid, name in vital_data])

    def queryset(self, request, queryset):
        """Return the object with a student of the right username."""
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        fields = [f.name for f in queryset.model._meta.get_fields()]
        if self.value() is None:
            return queryset
        if "vital" in fields:
            return queryset.filter(vital__VITAL_ID=self.value())
        if "VITAL" in fields:
            return queryset.filter(VITAL__VITAL_ID=self.value())


# Register your models here.


class VITAL_Test_MapInline(admin.StackedInline):
    """Inline Admin for Test Mapping for use with VITALs."""

    model = VITAL_Test_Map
    form = VITAL_Test_MapForm
    extra = 0
    fk_name = "test"


class VITAL_Test_Map_VITAL_Inline(admin.StackedInline):
    """Inline Admin for Test Mapping for use with VITALs."""

    model = VITAL_Test_Map
    form = VITAL_Test_MapForm
    extra = 0


class VITAL_ResultInline(admin.StackedInline):
    """Inline admin for Test Result mapping for VITALS."""

    model = VITAL_Result
    form = VITAL_ResultForm
    extra = 0

    def get_queryset(self, request):
        """Return optimised queryset with select_related to avoid N+1 queries."""
        return super().get_queryset(request).select_related("user", "vital", "vital__module")


class VITALInline(admin.StackedInline):
    """Inline admin for VITALS."""

    model = VITAL
    form = VITALForm
    extra = 0


add_inlines("accounts.Account", VITAL_ResultInline, "vital_results")
add_inlines("minerva.Test", VITAL_Test_MapInline, "vitals_mappings")
add_inlines("minerva.Module", VITALInline, "VITALS")


@admin.action(description="Force Update of VITAL")
def update_vital_users(modelAdmin, request, queryset):
    """Force an update of all users for the selected VITALs."""
    count = queryset.count()
    for vital in queryset.all():
        for student in vital.module.students.all():
            vital.passed(student)
            ss = student.summaries.filter(module=vital.module, category__text="VITALs").first()
            ss.save()
    modelAdmin.message_user(request, f"Updated VITAL status for {count} VITAL(s).", messages.SUCCESS)


@admin.register(VITAL)
class VITALAdmin(ImportExportModelAdmin):
    """Admin class for VITALs."""

    list_display = ("name", "module", "VITAL_ID")
    list_filter = ("name", ModuleListFilter(), "VITAL_ID")
    search_fields = ["name", "description", "module__name", "VITAL_ID"]
    list_select_related = ("module",)
    inlines = [VITAL_Test_Map_VITAL_Inline, VITAL_ResultInline]
    actions = [
        update_vital_users,
        "delete_vital_results",
        "create_vital_results",
    ]

    fieldsets = (
        (
            "Details",
            {
                "fields": ("name", "description", "module", "VITAL_ID"),
                "classes": ("baton-tabs-init", "baton-tab-inline-tests_mappings", "baton-tab-inline-student_results"),
            },
        ),
    )

    @admin.action(description="Delete all VITAL Results for selected VITALs")
    def delete_vital_results(self, request, queryset):
        """Delete all VITAL_Result objects associated with the selected VITALs.

        Args:
            request (HttpRequest):
                The current admin request.
            queryset (QuerySet):
                The selected VITAL objects.
        """
        deleted_count, _ = VITAL_Result.objects.filter(vital__in=queryset).delete()
        self.message_user(request, f"Deleted {deleted_count} VITAL result(s).")

    @admin.action(description="Create VITAL Results based on mapping conditions")
    def create_vital_results(self, request, queryset):
        """Create or update VITAL_Result objects based on VITAL mapping conditions.

        For each selected VITAL, checks whether each enrolled student has met the
        requirements defined by the VITAL mapping objects and creates or updates
        the corresponding VITAL_Result accordingly.

        Args:
            request (HttpRequest):
                The current admin request.
            queryset (QuerySet):
                The selected VITAL objects.
        """
        updated_count = 0
        for vital in queryset.select_related("module").prefetch_related("module__students"):
            if vital.module is None:
                continue
            for student in vital.module.students.all():
                if vital.check_vital(student):
                    updated_count += 1
        self.message_user(request, f"Created or updated {updated_count} VITAL result(s).")

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
    list_filter = (ModuleListFilter("test"), ModuleListFilter("vital"), "necessary", "sufficient")
    search_fields = ["test__name", "vital__name", "vital__module__code", "test__module__code"]
    list_select_related = ("test", "test__module", "vital", "vital__module")

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return VITAL_Test_MapResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return VITAL_Test_MapResource


@admin.register(VITAL_Result)
class VITAL_ResultAdmin(ImportExportModelAdmin):
    """Admin interface for VITAL Results."""

    list_display = ("vital", "user", "passed", "date_passed")
    list_editable = ("passed",)
    list_filter = (VITALListFilter, StudentListFilter, "passed", "date_passed")
    search_fields = ["vital__name", "user__first_name", "user__last_name", "user__username", "vital__module__code"]
    list_select_related = ("vital", "vital__module", "user")

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return VITAL_ResultResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return VITAL_ResultResource
