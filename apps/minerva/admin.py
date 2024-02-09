# Django imports
from django.contrib import admin, messages

# external imports
from import_export.admin import ImportExportMixin, ImportExportModelAdmin
from util.admin import add_inlines

# app imports
from .models import Module, Test, Test_Attempt, Test_Score
from .resource import (
    ModuleResource, Test_AttemptResource, Test_ScoreResource, TestResource,
)

# Register your models here.


class Test_ScoreInline(admin.StackedInline):
    """Inline admin for Test Result mapping for VITALS."""

    model = Test_Score
    extra = 0


class Test_AttemptInline(admin.StackedInline):
    """Inline admin for Test Result mapping for VITALS."""

    model = Test_Attempt
    extra = 0


add_inlines("accounts.Account", Test_ScoreInline, "test_results")


@admin.register(Module)
class ModuleAdmin(ImportExportModelAdmin):
    """Admin Class for Module objects."""

    list_display = ("id", "uuid", "courseId", "name")
    list_filter = list_display
    search_fields = ["name", "description", "programmes__name", "programmes__code"]

    actions = ["generate_marksheet"]

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
        "externalGrade",
        "score_possible",
        "grading_due",
        "release_date",
        "recommended_date",
        "grading_attemptsAllowed",
    )
    list_filter = list_display
    search_fields = ["name", "module__name", "module__programmes__name"]

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
