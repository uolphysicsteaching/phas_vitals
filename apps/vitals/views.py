"""Views for the VITALS and similar models from the vitals app."""

# Python imports
from collections import namedtuple

# Django imports
# Create your views here.
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils.html import format_html
from django.views.generic import DetailView, FormView

# external imports
from accounts.views import StudentSummaryView
from dal import autocomplete
from django_tables2 import SingleTableMixin
from django_tables2.columns import Column
from matplotlib import pyplot as plt
from minerva.forms import ModuleSelectForm
from minerva.models import ModuleEnrollment
from util.http import svg_data
from util.tables import BaseTable
from util.views import (
    IsStaffViewMixin,
    IsStudentViewixin,
    IsSuperuserViewMixin,
    RedirectView,
)

# app imports
from .models import VITAL

ImageData = namedtuple("ImageData", ["data", "alt"], defaults=["", ""])


class VITALResultColumn(Column):
    """Handles displaying test result information."""

    status_class_map = {
        "Started": "table-primary",
        "Finished": "table-secondary",
        "Not Started": "",
    }

    def __init__(self, **kargs):
        """Mark the header table to user vertical oriented text."""
        attrs = kargs.pop("attrs", {})
        vital = kargs.pop("vital")
        if vital is not None:
            attrs.update(
                {
                    "th": {
                        "class": f"vertical vital_link {self.status_class_map[vital.status]}",
                        "id": f"vital_{vital.pk}",
                    },
                }
            )
        else:
            attrs.update({"th": {"class": "vertical"}})
        kargs["attrs"] = attrs
        super().__init__(**kargs)

    def render(self, value):
        """Render the individual VITAL value."""
        match value:
            case None:
                ret = ""
            case {"passed": passed}:
                if passed is None:
                    ret = '<span class="badge bg-secondary">!</span>'
                elif passed:
                    ret = '<span class="badge bg-success">P</span>'
                else:
                    ret = '<span class="badge bg-danger">F</span>'
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
        """Construct instance variables."""
        self.module = None
        self.vitals = []
        self._entries = []
        super().__init__(*args, **kargs)

    @property
    def entries(self):
        """Cache entries between metrhods."""
        if len(self._entries) == 0:
            self._entries = self.get_entries()
        return self._entries

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
            attrs[vital.name] = VITALResultColumn(orderable=False, vital=vital)
            attrs["Overall"] = VITALResultColumn(orderable=False, vital=None)
        klass = type("DynamicTable", (self.table_class,), attrs)
        setattr(klass._meta, "row_attrs", {"class": "student_link"})
        return klass

    def get_context_data(self, **kwargs):
        """Get the cohort into context from the slug."""
        context = super().get_context_data(**kwargs)
        context["module"] = self.module
        return context

    def get_entries(Self):
        """Override this mewothd in actual classes."""
        raise NotImplementedError("You must supply a get_entries method.")

    def get_table_data(self):
        """Fill out the table with data, creating the entries for the MarkType columns to interpret."""
        table = []

        for entry in self.entries:
            record = {  # Standard student information entries
                "student": entry.student,
                "number": entry.student.SID,
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
            ModuleEnrollment.objects.filter(active=True, module=self.module)
            .prefetch_related("student", "student__vital_results", "student__programme", "status")
            .order_by("student__last_name", "student__first_name")
        )


class ShowTutorVitalResultsView(IsStaffViewMixin, BaseShowvitalResults):
    """Show all the student VITAL results."""

    def get_entries(self):
        """Get all module enrollments for the module."""
        return (
            ModuleEnrollment.objects.filter(
                active=True, module=self.module, student__tutorial_group__tutor=self.request.user
            )
            .prefetch_related("student", "student__vital_results", "student__programme", "status")
            .order_by("student__last_name", "student__first_name")
        )


class ShowVitralResultsView(RedirectView):
    """Endpoint for the VITALS results views."""

    superuser_view = ShowAllVitalResultsView
    staff_view = ShowTutorVitalResultsView

    def get_logged_in_view(self, request):
        """Patch in the kwargs with the user number."""
        self.kwargs["username"] = request.user.username
        self.kwargs["selected_tab"] = "#VITALS"
        return StudentSummaryView


class VitalDetailView(IsStudentViewixin, DetailView):
    """Provide a detail view for a single test."""

    template_name = "vitals/vital-detail.html"
    slug_field = "pk"
    slug_url_kwarg = "pk"
    model = VITAL
    context_object_name = "vital"

    def get_context_data(self, **kwargs):
        """Get plots as extra context data."""
        context = super().get_context_data(**kwargs)
        context["plot1"] = self._make_plots(context["vital"])
        return context

    def _make_plots(self, vital):
        """Make the figure for a Test's plots."""
        fig1, pie = plt.subplots(figsize=(3.5, 3.5))
        data = vital.stats
        colours = ["green", "red", "blue"]
        _, texts = pie.pie(list(data.values()), labels=list(data.keys()), colors=colours, labeldistance=0.3)
        for text in texts:
            text.set_bbox({"facecolor": (1, 1, 1, 0.75), "edgecolor": (1, 1, 1, 0.25)})
        plt.tight_layout()
        alt1 = f"{vital.name} Pass/Faile" + " ".join([f"{label}:{count}" for label, count in data.items()])
        plt.close("all")
        return ImageData(svg_data(fig1, base64=True), alt1)


class VITALAutocomplete(autocomplete.Select2QuerySetView):
    """Autocomplete lookup for VITALs."""

    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return VITAL.objects.none()

        qs = VITAL.objects.all()

        if self.q:
            qs = qs.filter(Q(name__icontains=self.q) | Q(VITAL_ID__icontains=self.q)).order_by("VITAL_ID")
        return qs
