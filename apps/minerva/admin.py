# Django imports
from django.contrib import admin, messages

# external imports
from import_export.admin import ImportExportModelAdmin
from util.admin import add_inlines

# app imports
from .models import (
    Module,
    ModuleEnrollment,
    StatusCode,
    Test,
    Test_Attempt,
    Test_Score,
)
from .resource import (
    ModuleEnrollmentReource,
    ModuleResource,
    StatusCodeResource,
    Test_AttemptResource,
    Test_ScoreResource,
    TestResource,
)

# Register your models here.


class Test_ScoreInline(admin.StackedInline):
    """Inline admin for Test Result mapping for VITALS."""

    model = Test_Score
    fields = ["user", "test", "score", "passed"]
    extra = 0


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


@admin.register(Module)
class ModuleAdmin(ImportExportModelAdmin):
    """Admin Class for Module objects."""

    list_display = ("id", "uuid", "courseId", "name")
    list_filter = list_display
    search_fields = ["name", "description", "programmes__name", "programmes__code"]
    iniines = [
        ModuleEnrollmentInline,
    ]
    actions = ["generate_marksheet"]

    fieldsets = (
        (
            "Basic Details",
            {
                "fields": (
                    ("uuid", "courseId", "parent_module"),
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
    list_filter = list_display
    search_fields = ["name", "module__name", "module__programmes__name"]
    inlines = [
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
    list_filter = list_display
    search_fields = ["user__last_name", "user__username", "test__name", "test__module__name"]
    inlines = [
        Test_AttemptInline,
    ]

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
    list_filter = list_display
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
