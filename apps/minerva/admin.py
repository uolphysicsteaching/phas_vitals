"""Admin interface classes for util app."""
# Django imports
from django.contrib import admin, messages
from django.contrib.flatpages.admin import FlatPageAdmin
from django.contrib.flatpages.models import FlatPage
from django.urls import reverse

# external imports
from dal_admin_filters import AutocompleteFilter
from import_export.admin import ImportExportModelAdmin
from tinymce.widgets import TinyMCE
from util.admin import add_inlines

# app imports
from .forms import Test_ScoreForm
from .models import (
    GradebookColumn,
    Module,
    ModuleEnrollment,
    StatusCode,
    Test,
    Test_Attempt,
    Test_Score,
)
from .resource import (
    GradebookColumnResource,
    ModuleEnrollmentReource,
    ModuleResource,
    StatusCodeResource,
    Test_AttemptResource,
    Test_ScoreResource,
    TestResource,
)

# Register your models here.


class ModuleFilter(AutocompleteFilter):
    """Lookup filter for module names."""

    title = "Module"  # filter's title
    field_name = "module"  # field name - ForeignKey to Country model
    autocomplete_url = "minerva:Module_lookup"  # url name of Country autocomplete view


class TestFilter(AutocompleteFilter):
    """Lookup filter for module names."""

    title = "Test"  # filter's title
    field_name = "test"  # field name - ForeignKey to Country model
    autocomplete_url = "minerva:Test_lookup"  # url name of Country autocomplete view


class Test_ScoreInline(admin.StackedInline):
    """Inline admin for Test Result mapping for VITALS."""

    model = Test_Score
    fields = ["user", "test", "score", "passed"]
    extra = 0
    form = Test_ScoreForm


class Test_AttemptInline(admin.StackedInline):
    """Inline admin for Test Result mapping for VITALS."""

    model = Test_Attempt
    extra = 0
    fieldsets = (
        (
            "Basic Details",
            {
                "fields": (
                    "test_entry",
                    ("status", "score"),
                    "text",
                    ("created", "attempted", "modified"),
                ),
            },
        ),
    )


class ModuleEnrollmentInline(admin.StackedInline):
    """Inline admin for module enrollments."""

    model = ModuleEnrollment
    extra = 0


add_inlines("accounts.Account", Test_ScoreInline, "test_results")
add_inlines("accounts.Account", ModuleEnrollmentInline, "module_enrollments")


class GradebookColumnInline(admin.StackedInline):
    """Inline Admin for GradebookColumns on Tests."""

    model = GradebookColumn
    extra = 0


@admin.register(Module)
class ModuleAdmin(ImportExportModelAdmin):
    """Admin Class for Module objects."""

    list_display = ("id", "year", "code", "courseId", "name")
    list_filter = list_display
    search_fields = ["name", "description", "module__year"]
    iniines = [
        ModuleEnrollmentInline,
    ]
    actions = ["generate_marksheet", "update_tests"]

    fieldsets = (
        (
            "Basic Details",
            {
                "fields": (
                    ("uuid", "courseId", "parent_module", "year"),
                    ("code", "alt_code", "exam_code"),
                    "name",
                    ("credits", "level", "semester"),
                    "description",
                    ("module_leader", "team_members"),
                    ("updater",),
                ),
                "classes": [
                    "baton-tabs-init",
                    "baton-tab-inline-student_enrollments",
                ],
            },
        ),
    )

    @admin.action(description="Generate Marksheet")
    def generate_marksheet(self, request, queryset):
        """Call the makrsheet generation method for the selected module."""
        if queryset.count() == 1:
            return queryset.first().generate_marksheet()
        self.message_user(
            request,
            "Can only generate a marksheet for a single module at this tyime",
            level=messages.ERROR,
            extra_tags="",
            fail_silently=False,
        )
        queryset.update(status="p")

    @admin.action(description="Generate Tests for module")
    def update_tests(self, request, queryset):
        """Call the makrsheet generation method for the selected module."""
        for module in queryset.all():
            Test.create_or_update_from_json(module)

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return ModuleResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return ModuleResource


@admin.register(Test)
class TestAdmin(ImportExportModelAdmin):
    """Admin Class for Test objects."""

    list_display = (
        "test_id",
        "module",
        "name",
        "type",
        "score_possible",
        "passing_score",
        "grading_due",
        "release_date",
        "recommended_date",
        "grading_attemptsAllowed",
    )
    list_editable = [
        "type",
        "score_possible",
        "passing_score",
        "grading_due",
        "release_date",
        "recommended_date",
    ]
    list_filter = (
        "module",
        "type",
        "grading_due",
        "release_date",
        "recommended_date",
    )
    search_fields = ["name", "module__name", "module__year__name"]
    inlines = [
        GradebookColumnInline,
        Test_ScoreInline,
    ]
    fieldsets = (
        (
            "Basic Details",
            {
                "fields": (
                    (
                        "test_id",
                        "module",
                    ),
                    (
                        "type",
                        "name",
                    ),
                    "description",
                    "score_possible",
                    "passing_score",
                    "grading_attemptsAllowed",
                ),
                "classes": [
                    "baton-tabs-init",
                    "baton-tab-fs-dates",
                    "baton-tab-inline-results",
                ],
            },
        ),
        (
            "Dates",
            {
                "fields": ("grading_due", "release_date", "recommended_date"),
                "classes": ("tab-fs-dates",),
            },
        ),
    )

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return TestResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return TestResource


@admin.register(GradebookColumn)
class GradebookColumnAdmin(ImportExportModelAdmin):
    """Admin class for Gradebook columns."""

    list_display = ("gradebook_id", "name", "test")
    list_filter = ["test"]
    search_fields = ["gradebook_id", "name", "test__name", "test__test_id", "test__module__code", "test__module__name"]

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return GradebookColumnResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return GradebookColumnResource


@admin.register(Test_Score)
class Test_ScoreAdmin(ImportExportModelAdmin):
    """Admin Class for Module objects."""

    list_display = (
        "user",
        "test",
        "status",
        "score",
        "passed",
    )
    list_filter = (
        "user",
        TestFilter,
        "status",
        "score",
        "passed",
    )
    search_fields = ["user__last_name", "user__username", "test__name", "test__module__name"]
    inlines = [
        Test_AttemptInline,
    ]
    form = Test_ScoreForm
    fieldsets = (
        (
            "Basic Details",
            {
                "fields": (
                    ("user", "test"),
                    ("status", "score", "passed"),
                    "text",
                ),
                "classes": [
                    "baton-tabs-init",
                    "baton-tab-inline-attempts",
                ],
            },
        ),
    )

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return Test_ScoreResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return Test_ScoreResource


@admin.register(Test_Attempt)
class Test_AtemptAdmin(ImportExportModelAdmin):
    """Admin Class for Module objects."""

    list_display = (
        "attempt_id",
        "test_entry",
        "status",
        "score",
        "created",
        "attempted",
        "modified",
    )
    list_filter = list_display
    search_fields = [
        "test_entry__user__last_name",
        "test_entry__user__username",
        "test_entry__test__name",
        "test_entry__test__module__name",
    ]

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return Test_AttemptResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return Test_AttemptResource


@admin.register(StatusCode)
class StatusCodeAdmin(ImportExportModelAdmin):
    """Admin Class for Status Code Resources."""

    list_display = ["code", "explanation", "capped", "valid", "resit", "level"]
    list_filter = list_display
    search_fields = list_filter[:2] + ["level"]

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return StatusCodeResource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return StatusCodeResource


@admin.register(ModuleEnrollment)
class ModuleEnrollmentAdmin(ImportExportModelAdmin):
    """Admin interface for ModuleEnrollment objects."""

    list_display = ("module", "student", "status")
    list_filter = (ModuleFilter, "student", "status")
    search_fields = [
        "module__name",
        "module__code",
        "student__last_name",
        "student__first_name",
        "student__username",
        "status__code",
        "status__explanation",
    ]

    def get_export_resource_class(self):
        """Return the class for exporting objects."""
        return ModuleEnrollmentReource

    def get_import_resource_class(self):
        """Return the class for importing objects."""
        return ModuleEnrollmentReource


admin.site.unregister(FlatPage)


@admin.register(FlatPage)
class TinyMCEFlatPageAdmin(FlatPageAdmin):
    list_display = ["url", "title", "enable_comments"]
    list_filters = ["url", "title", "enable_comments"]
    suit_list_filter_horizontal = ["url", "title", "enable_comments"]

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "content":
            ret = db_field.formfield(
                widget=TinyMCE(
                    attrs={"cols": 80, "rows": 30},
                    mce_attrs={"external_link_list_url": reverse("tinymce-linklist")},
                )
            )
            return ret
        return super().formfield_for_dbfield(db_field, **kwargs)
