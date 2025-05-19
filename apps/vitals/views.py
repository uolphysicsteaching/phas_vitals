"""Views for the VITALS and similar models from the vitals app."""

# Python imports
from collections import namedtuple

# Django imports
# Create your views here.
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import OuterRef, Q, Subquery
from django.utils.html import format_html
from django.views.generic import DetailView, FormView

# external imports
from accounts.models import Account
from accounts.views import StudentSummaryView
from dal import autocomplete
from django_tables2 import SingleTableMixin
from django_tables2.columns import Column
from django_tables2.paginators import LazyPaginator
from htmx_views.views import HTMXProcessMixin
from matplotlib import pyplot as plt
from minerva.forms import VITALsModuleSelectForm as ModuleSelectForm
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
from .models import VITAL, VITAL_Result

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
            case VITAL_Result():
                if value.passed is None:
                    ret = '<span class="badge bg-secondary">!</span>'
                elif value.passed:
                    ret = '<span class="badge bg-success">P</span>'
                else:
                    ret = '<span class="badge bg-danger">F</span>'
            case {"passed": passed}:
                if passed is None:
                    ret = '<span class="badge bg-secondary">!</span>'
                elif passed:
                    ret = '<span class="badge bg-success">P</span>'
                else:
                    ret = '<span class="badge bg-danger">F</span>'
            case _:
                ret = str(value)

        return format_html(ret)


class BaseShowvitalResults(SingleTableMixin, HTMXProcessMixin, FormView):
    """View to show vital results for a module in a table."""

    form_class = ModuleSelectForm
    paginator_class = LazyPaginator
    table_class = BaseTable
    template_name = "vitals/vital_results.html"
    template_name_next_batch = "vitals/parts/vital_results_next_batch.html"
    table_pagination = {"per_page": 10}
    context_table_name = "vital_results"

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
            self.vitals = VITAL.objects.filter(module=self.module).order_by("tests__type", "start_date", "name")
        self.page = int(self.request.GET.get("page", 1))
        return self.render_to_response(self.get_context_data())

    def get_table_class(self):
        """Construct the django-tables2 table class for this view."""
        attrs = {}
        for vital in self.vitals:
            attrs[vital.name] = VITALResultColumn(orderable=False, vital=vital)
            attrs["Overall"] = VITALResultColumn(orderable=False, vital=None)
        klass = type("DynamicTable", (self.table_class,), attrs)
        setattr(klass._meta, "row_attrs", {"class": "student_link"})
        setattr(klass._meta, "template_name", "util/table.html")
        return klass

    def get_context_data(self, **kwargs):
        """Get the cohort into context from the slug."""
        context = super().get_context_data(**kwargs)
        context["module"] = self.module
        return context

    def get_context_data_next_batch(self, **kwargs):
        ret = self.get_context_data(**kwargs)
        return ret

    def get_entries(Self):
        """Override this mewothd in actual classes."""
        raise NotImplementedError("You must supply a get_entries method.")

    def get_table_data(self):
        """Fill out the table with data, creating the entries for the MarkType columns to interpret."""
        vitals = {vital.name: vital.pk for vital in self.vitals}
        table = [Row_Dict(student, vitals, self.module) for student in self.entries]
        return table

    def get_queryset(self):
        """Use get_table_data instead of a queryset."""
        return self.get_table_data()


class Row_Dict:
    """Proxy for a dictionary that delays evaluating the test results."""

    def __init__(self, student, vitals, module):
        self.student = student
        self.vital_results = student.vital_results.filter(vital__module=module).all()
        self.vitals = vitals
        dd = self.__dict__

    def __getitem__(self, index):
        match index:
            case "student":
                return self.student
            case "SID":
                return self.student.number
            case "programme":
                return self.student.programme.name
            case "status":
                return self.student.status
            case "Overall":
                if self.vital_results.count() != len(self.vitals):
                    return {"passed": None}
                if self.vital_results.filter(passed=False).count() > 0:
                    return {"passed": False}
                return {"passed": True}
            case vital if vital in self.vitals:
                try:
                    return self.vital_results.get(vital__pk=self.vitals[vital])
                except ObjectDoesNotExist:
                    return None
            case _:
                return False


class ShowAllVitalResultsView(IsSuperuserViewMixin, BaseShowvitalResults):
    """Show all the student VITAL results."""

    def get_entries(self):
        """Get all module enrollments for the module."""
        if not getattr(self, "page", False):
            return Account.objects.none()
        enroillments = ModuleEnrollment.objects.filter(module=self.module, active=True).values("id")
        status = enroillments.filter(student=OuterRef("pk")).values("status__code")
        qs = (
            Account.objects.filter(module_enrollments__in=enroillments)
            .annotate(status=Subquery(status))
            .select_related("programme")
            .prefetch_related("vital_results")
            .order_by("last_name", "first_name")
        )
        return qs


class ShowTutorVitalResultsView(IsStaffViewMixin, BaseShowvitalResults):
    """Show all the student VITAL results."""

    def get_entries(self):
        """Get all module enrollments for the module."""
        if not getattr(self, "page", False):
            return Account.objects.none()
        enroillments = ModuleEnrollment.objects.filter(module=self.module, active=True).values("id")
        status = enroillments.filter(student=OuterRef("pk")).values("status__code")
        qs = (
            Account.objects.filter(module_enrollments__in=enroillments, tutorial_group__tutor=self.request.user)
            .annotate(status=Subquery(status))
            .select_related("programme")
            .prefetch_related("vital_results")
            .order_by("last_name", "first_name")
        )
        return qs


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
