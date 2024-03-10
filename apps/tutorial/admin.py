# Django imports
from django import forms
from django.contrib.admin import SimpleListFilter, StackedInline, register

# external imports
from import_export.admin import ImportExportModelAdmin
from util.admin import CohortListFilter, StaffListFilter, StudentListFilter

# app imports
from . import resources
from .forms import TutorialAssignmentForm
from .models import (
    Attendance,
    Meeting,
    MeetingAttendance,
    Session,
    SessionType,
    Tutorial,
    TutorialAssignment,
)


def title(t):
    """Make t into Title case."""
    return t.title()


class TutorialListFilter(SimpleListFilter):
    """Admin Filter for Tutorials."""

    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = "Tutorial Group"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "tutorial"

    def lookups(self, request, model_admin):
        """Return a sorted list of Tutor group names."""
        res = Tutorial.objects.all().order_by("-cohort__name", "code")
        return tuple([(x.code, x) for x in res])

    def queryset(self, request, queryset):
        """Return the object with a student of the right username."""
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        if self.value() is None:
            return queryset
        fields = [f.name for f in queryset.model._meta.get_fields()]
        if "tutorial_group" in fields:
            return queryset.filter(tutorial_group__code=self.value())
        elif "tutorial" in fields:
            return queryset.filter(tutorial__code=self.value())
        elif "student" in fields:
            return queryset.filter(student__tutorial_group__code=self.value())
        else:
            raise ValueError(f"Can't work out field for {fields}")


@register(TutorialAssignment)
class TutorialAssignmentAdmin(ImportExportModelAdmin):
    """Admin class for Tutorial Assignment."""

    list_display = ("tutorial", "student", "integrity_test", "pebblepad_form")
    list_filter = ("tutorial", StudentListFilter, "integrity_test", "pebblepad_form")
    search_fields = [
        "student__first_name",
        "student__last_name",
        "student__username",
        "student__number",
        "tutorial__code",
        "tutorial__tutor__last_name",
    ]
    form = TutorialAssignmentForm

    def get_export_resource_class(self):
        """Set the export resource class."""
        return resources.TutorialAssignmentResource

    def get_import_resource_class(self):
        """Set the import resource class."""
        return resources.TutorialAssignmentResource


class TutorialAdminForm(forms.ModelForm):
    """Form for managing tutorial groups."""

    class Meta:
        model = Tutorial
        exclude = []

    def __init__(self, *args, **kwargs):
        """Limit tutor to the correct queryset."""
        super().__init__(*args, **kwargs)
        self.fields["tutor"].queryset = self.fields["tutor"].queryset.order_by("last_name", "first_name")


class TutorialAdminInlineForm(forms.ModelForm):
    """Inline admin form class for tutorial groups."""

    class Meta:
        model = Tutorial
        exclude = ("tutor",)


class TutorialAssignmentInlineForm(forms.ModelForm):
    """Inline admin form class for Tutorial Assignment."""

    class Meta:
        model = TutorialAssignment
        exclude = ("tutorial",)


class TutorialAdminInline(StackedInline):
    """Inline admin class for Tutorial Group."""

    model = Tutorial
    verbose_name = "Tutorial Group"
    extra = 1
    max_num = 2
    form = TutorialAdminInlineForm
    fk_name = "tutor"


class TutorialAssignmentInline(StackedInline):
    """Inline admin class for tutorial assignment."""

    model = TutorialAssignment
    verbose_name = "Tutee"
    verbose_name_plural = "Tutees"
    extra = 1
    form = TutorialAssignmentInlineForm
    suit_classes = "suit-tab suit-tab-students"


@register(Tutorial)
class TutorialAdmin(ImportExportModelAdmin):
    """Tutorial admin class."""

    list_display = ("code", "tutor", "numStudents", "cohort")
    list_filter = (StaffListFilter, CohortListFilter)
    search_fields = [
        "tutor__first_name",
        "tutor__last_name",
        "tutor__username",
        "cohort__name",
        "code",
        "students__number",
    ]

    form = TutorialAdminForm
    inlines = (TutorialAssignmentInline,)

    def get_export_resource_class(self):
        """Set the export resource class."""
        return resources.TutorialsResource

    def get_import_resource_class(self):
        """Set the import resource class."""
        return resources.TutorialsResource


@register(SessionType)
class SessionTypeAdmin(ImportExportModelAdmin):
    """Admin class for tutrial session types."""

    list_display = ("name",)
    list_filter = ("name",)
    search_fields = ("name", "description")

    def get_export_resource_class(self):
        """Set the export resource class."""
        return resources.SessionTypeResource

    def get_import_resource_class(self):
        """Set the import resource class."""
        return resources.SessionTypeResource


@register(Session)
class SessionAdmin(ImportExportModelAdmin):
    """Tutorial Session admin class."""

    list_display = ("cohort", "semester", "name", "start", "end")
    list_filter = (CohortListFilter, "semester", "name", "start", "end")
    search_fields = ("name", "cohort__name")

    def get_export_resource_class(self):
        """Set the export resource class."""
        return resources.SessionResource

    def get_import_resource_class(self):
        """Set the import resource class."""
        return resources.SessionResource


@register(Attendance)
class AttendanceAdmin(ImportExportModelAdmin):
    """Tutorial Attendance Admin Class."""

    list_display = ("student", "session", "type", "score")
    list_filter = (StudentListFilter, CohortListFilter, TutorialListFilter, "session", "type", "score")
    search_fields = (
        "student__first_name",
        "student__last_name",
        "student__username",
        "student__number",
        "session__name",
        "type__name",
    )

    def get_export_resource_class(self):
        """Set the export resource class."""
        return resources.AttendanceResource

    def get_import_resource_class(self):
        """Set the import resource class."""
        return resources.AttendanceResource


@register(MeetingAttendance)
class MeetingAttendanceAdmin(ImportExportModelAdmin):
    """Admin class for Meeting Attendance."""

    list_display = ("student", "meeting", "tutor", "submitted")
    list_filter = (StudentListFilter, "meeting", StaffListFilter, "submitted")
    search_fields = (
        "student__first_name",
        "student__last_name",
        "student__username",
        "student__number",
        "meeting__name",
    )

    def get_export_resource_class(self):
        """Set the export resource class."""
        return resources.MeetingAttendanceResource

    def get_import_resource_class(self):
        """Set the import resource class."""
        return resources.MeetingAttendanceResource


@register(Meeting)
class MeetingAdmin(ImportExportModelAdmin):
    """Admin class for tutorial meetings."""

    list_display = ("name", "cohort", "due_date")
    list_filter = ("name", CohortListFilter, "due_date")
    search_fields = ("name", "cohort__name")

    def get_export_resource_class(self):
        """Set the export resource class."""
        return resources.MeetingResource

    def get_import_resource_class(self):
        """Set the import resource class."""
        return resources.MeetingResource
