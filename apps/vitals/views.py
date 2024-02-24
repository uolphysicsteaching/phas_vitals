# Python imports

# Django imports
# Create your views here.
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import format_html
from django.views.generic import DetailView, FormView
from django.views.generic.edit import FormMixin

# external imports
from django_tables2 import SingleTableMixin
from django_tables2.columns import Column
from minerva.forms import ModuleSelectForm
from minerva.models import ModuleEnrollment
from util.tables import BaseTable
from util.views import (
    IsStaffViewMixin,
    IsStudentViewixin,
    IsSuperuserViewMixin,
    RedirectView,
)


class VITALResultColumn(Column):
    """Handles displaying test result information."""

    def __init__(self, **kargs):
        """Mark the header table to user vertical oriented text."""
        attrs = kargs.pop("attrs", {})
        attrs.update({"th": {"class": "vertical"}})
        kargs["attrs"] = attrs
        super().__init__(**kargs)

    def render(self, value):
        match value:
            case None:
                ret = ""
            case {"passed": passed}:
                if passed:
                    ret = f'<span class="badge bg-success">P</span>'
                else:
                    ret = f'<span class="badge bg-danger">F</span>'
            case _:
                ret = value

        return format_html(ret)


class BaseShowvitalResults(SingleTableMixin, FormView):
    """View to show vital results for a module in a table."""

    form_class = ModuleSelectForm
    table_class = BaseTable
    template_name = "vitals/vital_results.html"
    context_table_name = "vital_results"
    table_pagination = False

    def __init__(self, *args, **kargs):
        """Setup instance variables."""
        self.module = None
        self.vitals = []
        super().__init__(*args, **kargs)

    def form_valid(self, form):
        """Update self.module with the module selected in the form."""
        self.module = form.cleaned_data["module"]
        if self.module is not None:
            self.vitals = self.module.VITALS.all().order_by("start_date", "name")
        return self.render_to_response(self.get_context_data())

    def get_table_class(self):
        """Construct the django-tables2 table class for this view."""
        attrs = {}
        for vital in self.vitals:
            attrs[vital.name] = VITALResultColumn(orderable=False)
            attrs["Overall"] = VITALResultColumn(orderable=False)
        klass = type("DynamicTable", (self.table_class,), attrs)
        return klass

    def get_context_data(self, **kwargs):
        """Get the cohort into context from the slug."""
        context = super().get_context_data(**kwargs)
        context["module"] = self.module
        return context

    def get_entries(Self):
        """Override this mewothd in actuall classes."""
        raise NotImplementedError("You must supply a get_entries method.")

    def get_table_data(self):
        """Fill out the table with data, creating the entries for the MarkType columns to interpret."""
        table = []
        entries = self.get_entries()

        for entry in entries:
            record = {  # Standard student information entries
                "student": entry.student.display_name,
                "number": entry.student.number,
                "programme": entry.student.programme.name,
                "status": entry.status.code,
                "Overall": {"passed": entry.passed_vitals},
            }
            for vital in self.vitals:  # Add columns for the vitals
                try:
                    ent = entry.student.vital_results.get(vital=vital)
                    record[vital.name] = {x: getattr(ent, x) for x in ["passed"]}
                except ObjectDoesNotExist:
                    record[vital.name] = None

            table.append(record)
        return table

    def get_queryset(self):
        """Use get_table_data instead of a queryset."""
        return self.get_table_data()


class ShowAllVitalResultsView(IsSuperuserViewMixin, BaseShowvitalResults):
    """Show all the student VITAL results."""

    def get_entries(self):
        """Get all module enrollments for the module."""
        return (
            ModuleEnrollment.objects.filter(module=self.module)
            .prefetch_related("student", "student__vital_results", "student__programme", "status")
            .order_by("student__last_name", "student__first_name")
        )


class ShowTutorVitalResultsView(IsStaffViewMixin, BaseShowvitalResults):
    """Show all the student VITAL results."""

    def get_entries(self):
        """Get all module enrollments for the module."""
        return (
            ModuleEnrollment.objects.filter(module=self.module, student__apt=self.request.user)
            .prefetch_related("student", "student__vital_results", "student__programme", "status")
            .order_by("student__last_name", "student__first_name")
        )


class ShowMyVitalResultsView(IsStudentViewixin, FormMixin, DetailView):
    """TODO write the individual student VITALs view."""


class ShowVitralResultsView(RedirectView):
    """Endpoint for the VITALS results views."""

    superuser_view = ShowAllVitalResultsView
    staff_view = ShowTutorVitalResultsView
    logged_in_view = ShowMyVitalResultsView
