"""View classes for the app that handles Minerva integration."""

# Python imports
import csv
import re
from collections import namedtuple
from textwrap import shorten
from traceback import format_exc

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.db.utils import IntegrityError
from django.forms import ValidationError
from django.http import StreamingHttpResponse
from django.utils.html import format_html
from django.views.generic import DetailView, FormView

# external imports
import numpy as np
import pandas as pd
from accounts.models import Account, Cohort
from accounts.views import StudentSummaryView
from dal import autocomplete
from django_tables2 import SingleTableMixin
from django_tables2.columns import Column
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.style import context as plot_context
from pytz import timezone
from util.http import buffer_to_base64, svg_data
from util.tables import BaseTable
from util.views import (
    IsStaffViewMixin,
    IsStudentViewixin,
    IsSuperuserViewMixin,
    RedirectView,
)

# app imports
from .forms import (
    ModuleSelectForm,
    ModuleSelectPlusForm,
    TestHistoryImportForm,
    TestImportForm,
)
from .models import Module, ModuleEnrollment, Test, Test_Attempt, Test_Score

TZ = timezone(settings.TIME_ZONE)

ImageData = namedtuple("ImageData", ["data", "alt"], defaults=["", ""])


def _delimiter(filename):
    """Return the delimiter of a file."""
    for enc in ["utf-8", "utf-16"]:
        try:
            with open(filename, "r", encoding=enc) as data:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(data.readline())
                if dialect.delimiter == "\x00":
                    raise UnicodeError
                return dialect.delimiter, enc
        except UnicodeError:
            continue


# Create your views here.
class ImportTestsView(IsSuperuserViewMixin, FormView):
    """Handles uploading the full Gtradebook."""

    template_name = "minerva/import_tests.html"
    form_class = TestImportForm
    success_url = "/minerva/import_tests/"


class StreamingImportTestsView(ImportTestsView):
    """A streaming response version of the full grade centre processor."""

    data = []

    test_name = re.compile(r"(?P<name>.*)\s\[Total\ Pts\:\s(?P<total>[0-9\.]+)\sScore\]\s\|(?P<test_id>.*)")

    def post(self, request, *args, **kwargs):
        """Handle form posting with cutsom work around exceptions."""
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist("upload_file")
        if form.is_valid():
            if len(files) < 1:
                raise ValidationError("Expecting one or more files.")
            try:
                for f in files:
                    try:
                        df = pd.read_excel(f.temporary_file_path())
                    except ValueError:
                        delimiter, enc = _delimiter(f.temporary_file_path())
                        df = pd.read_csv(f.temporary_file_path(), delimiter=delimiter, encoding=enc)
                    df.filename = f
                    self.data.append(df)
            except AssertionError:
                raise
            except Exception as e:
                form.add_error(
                    None,
                    f"Could not read Full Gradebook file due to: {e} with {f.temporary_file_path()} {format_exc()}",
                )
                return self.form_invalid(form)
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Process the uploaded Gradebook data."""
        self.form = form
        response = StreamingHttpResponse(iter(self.response_generator()))
        response["Content-Type"] = "text/plain"
        return response

    def response_generator(self):
        """Yield rows for a table."""
        module = self.form.cleaned_data["module"]
        alt = False
        for df in self.data:
            for col in df.columns:
                if match := self.test_name.search(col):
                    name = match.groupdict()["name"]
                    test_id = match.groupdict()["test_id"]
                    possible = float(match.groupdict()["total"])
                    test, new = Test.objects.get_or_create(test_id=test_id, module=module)
                    cls = "light" if not alt else "secondary"
                    alt = not alt
                    if new:
                        test.name = name
                        test.score_possible = possible
                        test.passing_score = 0.8 * possible
                        test.save()
                        yield f"<tr class='tb-{cls}'><td>Saving new test {name} {possible=} {test_id=}</td></tr>"
                    else:
                        test.name = name
                        test.score_possible = possible
                        test.passing_score = 0.8 * possible
                        test.save()

                        yield f"<tr class='tb-success'><td>ound existing column {name} {test_id=}</td></tr>"
                else:
                    yield f"<tr class='tb-warning'><td>Unmatched column name {col}</td></tr>"
            for _, row in df.iterrows():
                if row["Availability"] == "No" or np.isnan(row["Student ID"]):
                    continue
                first_name = row["First Name"]
                last_name = row["Last Name"]
                sid = int(row["Student ID"])
                username = row["Username"]
                user, _new = Account.objects.get_or_create(username=username)
                user.first_name = first_name
                user.last_name = last_name
                user.number = sid
                user.save()
                ModuleEnrollment.objects.get_or_create(module=self.module, student=user)
                for mod in self.module.sub_modules.all():
                    ModuleEnrollment.objects.get_or_create(module=mod, student=user)
                cls = "light" if not alt else "secondary"
                alt = not alt
                if new:
                    yield f"<tr class='tb-success'><td>New user {user.display_name} created</tr></td>"
                else:
                    yield f"<tr class='tb-{cls}'><td>Existing user {user.display_name} updated</td></tr>"


class ImportTestHistoryView(IsSuperuserViewMixin, FormView):
    """Handles uploading the Gradebook Hisotry Files."""

    template_name = "minerva/import_history.html"
    form_class = TestHistoryImportForm
    success_url = "/minerva/import_history/"


class StreamingImportTestsHistoryView(ImportTestHistoryView):
    """Streaming version of the ImportTestHistoryView."""

    data = []

    def post(self, request, *args, **kwargs):
        """Handle form posting with cutsom work around exceptions."""
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist("upload_file")
        if form.is_valid():
            if len(files) < 1:
                raise ValidationError("Expecting one or more files.")
            try:
                for f in files:
                    try:
                        df = pd.read_excel(f.temporary_file_path())
                    except ValueError:
                        delimiter, enc = _delimiter(f.temporary_file_path())
                        df = pd.read_csv(f.temporary_file_path(), delimiter=delimiter, encoding=enc)
                    df.filename = f
                    self.data.append(df)
            except AssertionError:
                raise
            except Exception as e:
                form.add_error(
                    None,
                    (
                        f"Could not read Gradebook History  file due to: {e} with"
                        + " {f.temporary_file_path()} {format_exc()}"
                    ),
                )
                return self.form_invalid(form)
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Process the uploaded Gradebook data."""
        self.form = form
        response = StreamingHttpResponse(iter(self.response_generator()))
        response["Content-Type"] = "text/plain"
        return response

    def response_generator(self):
        """Yield rows for a table."""
        module = self.form.cleaned_data["module"]
        alt = False
        for df in self.data:
            df.Date = pd.to_datetime(df.Date)
            df["AttemptDate"] = pd.to_datetime(df["Attempt Activity"])
            df["AttemptDate"] = df.AttemptDate.apply(TZ.localize)
            if df["Date"][0].tzinfo is None:
                df["Date"] = df.Date.apply(TZ.localize)
            for _, row in df.iterrows():
                try:
                    student = Account.objects.get(username=row.Username)
                except ObjectDoesNotExist:
                    print("Yield")
                    yield f"<tr class='tb-warning'><td>Unknown User {row.Username}</td></tr>"
                    continue
                try:
                    test = Test.objects.get(name=row.Column, module=module)
                except ObjectDoesNotExist:
                    print("Yield")
                    yield "<tr class='tb-warning'><td>Unknown test {row.Column}</td></tr>"
                    continue
                test_score, new = Test_Score.objects.get_or_create(user=student, test=test)
                new_id = f"{row.Column}:{row.Username}:{row.AttemptDate}"
                test_attempt, new = Test_Attempt.objects.get_or_create(attempt_id=new_id, test_entry=test_score)
                if (
                    not new
                    and test_attempt.score is not None
                    and not np.isnan(test_attempt.score)
                    and np.isnan(row.Value)
                ):
                    continue  # Skip over duplicate attempts where the score is NaN
                test_attempt.score = row.Value
                test_attempt.modified = row.Date
                test_attempt.attempted = row.AttemptDate
                try:
                    test_attempt.save()
                except IntegrityError:
                    yield f"<r class='bg tb-danger'><td>Database error for {test_attempt}</td></tr>"
                    continue
                cls = "light" if not alt else "secondary"
                alt = not alt
                yield (
                    f"<tr class='tb-{cls}'><td>Attempt {row.Column} for {row.Username} at {row.AttemptDate}"
                    + f" saved with score {row.Value}</td></tr>"
                )


class TestResultColumn(Column):
    """Handles displaying test result information."""

    status_class_map = {
        "Overdue": "table-warning",
        "Released": "table-primary",
        "Finished": "table-secondary",
        "Not Started": "",
    }

    def __init__(self, **kargs):
        """Mark the header table to user vertical oriented text."""
        attrs = kargs.pop("attrs", {})
        test = kargs.pop("test")
        attrs.update(
            {
                "th": {"class": f"vertical test_link {self.status_class_map[test.status]}", "id": f"{test.pk}"},
            }
        )
        kargs["attrs"] = attrs
        self.mode = kargs.pop("mode", "score")
        super().__init__(**kargs)

    def render(self, value):
        """Render the cell values."""
        match value:
            case False:
                ret = '<div class="badge rounded-pil bg-secondary">&nbsp;</div>'
            case Test_Score():
                if self.mode == "score":
                    ret = self.format_score(value)
                elif self.mode == "attempts":
                    ret = self.format_attempts(value)
            case _:
                ret = f'<div class="badge rounded-pil bg-secondary">{value}</div>'

        return format_html(ret)

    def format_score(self, test_score):
        """Format the html for a score."""
        passed = test_score.passed
        score = test_score.score
        attempted = test_score.attempts.count()
        for _, (attempts, colour) in settings.TESTS_ATTEMPTS_PROFILE[test_score.standing].items():
            if attempts < 0 or attempts >= attempted:
                bg_color = colour
                break
        else:
            bg_color = "white"
        if passed:
            return f'<div class="badge rounded-pil" style="background-color: {bg_color};">{score:.1f}</div>'
        if score is None or np.isnan(score):
            return f'<div class="badge rounded-pil" style="background-color: dimgrey;">&nbsp;!&nbsp;</div>'
        return f'<div class="badge rounded-pil"  style="background-color: {bg_color};">{score:.1f}</div>'

    def format_attempts(self, test_score):
        """Format some html for counting attempts at passing."""
        bi_class = "bi bi-emoji-smile" if test_score.passed else "bi bi-emoji-frown"
        attempted = test_score.attempts.count()
        for _, (attempts, colour) in settings.TESTS_ATTEMPTS_PROFILE[test_score.standing].items():
            if attempts < 0 or attempts >= attempted:
                bg_color = colour
                break
        else:
            bg_color = "white"
        return (
            f'<div class="badge rounded-pil {bi_class}" style="background-color: {bg_color};">&nbsp;{attempted}</div>'
        )


class BaseShowTestResultsView(SingleTableMixin, FormView):
    """Most of the machinery to show a table of student test results."""

    form_class = ModuleSelectPlusForm
    table_class = BaseTable
    template_name = "minerva/test_results.html"
    context_table_name = "test_results"
    table_pagination = False

    def __init__(self, *args, **kargs):
        """Construct instance variables."""
        self.module = None
        self.mode = "scor3e"
        self.type = "homework"
        self.tests = []
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
        self.mode = form.cleaned_data.get("mode", "score")
        self.type = form.cleaned_data.get("type", "homework")
        if self.module is not None:
            self.tests = self.module.tests.filter(type=self.type).order_by("release_date", "name")
        return self.render_to_response(self.get_context_data())

    def get_table_class(self):
        """Construct the django-tables2 table class for this view."""
        attrs = {}
        for test in self.tests:
            attrs[shorten(test.name, width=30)] = TestResultColumn(orderable=False, mode=self.mode, test=test)
        klass = type("DynamicTable", (self.table_class,), attrs)
        setattr(klass._meta, "row_attrs", {"class": "student_link"})
        return klass

    def get_context_data(self, **kwargs):
        """Get the cohort into context from the slug."""
        context = super().get_context_data(**kwargs)
        context["module"] = self.module
        return context

    def get_entries(self):
        """Override to return the data required."""
        raise NotImplementedError("Need to override the get_entries method.")

    def get_table_data(self):
        """Fill out the table with data, creating the entries for the MarkType columns to interpret."""
        table = []

        for entry in self.entries:
            record = {  # Standard student information entries
                "student": entry.student,
                "number": entry.student.SID,
                "programme": entry.student.programme.name,
                "status": entry.status.code,
            }
            for test in self.tests:  # Add columns for the tests
                try:
                    ent = entry.student.test_results.get(test=test)
                    record[shorten(test.name, width=30)] = ent
                except ObjectDoesNotExist:
                    record[test.name] = None

            table.append(record)
        return table

    def get_queryset(self):
        """Use get_table_data instead of a queryset."""
        return self.get_table_data()


class ShowAllTestResultsViiew(IsSuperuserViewMixin, BaseShowTestResultsView):
    """Show a table of all student test results."""

    def get_entries(self):
        """Get the students to include in the table."""
        return (
            ModuleEnrollment.objects.filter(active=True, module=self.module)
            .prefetch_related("student", "student__test_results", "student__programme", "status")
            .order_by("student__last_name", "student__first_name")
        )


class ShowTutorTestResultsViiew(IsStaffViewMixin, BaseShowTestResultsView):
    """Show a table of student test results for the current user's tutees."""

    def get_entries(self):
        """Get the students to include in the table."""
        return (
            ModuleEnrollment.objects.filter(
                active=True, module=self.module, student__tutorial_group__tutor=self.request.user
            )
            .prefetch_related("student", "student__test_results", "student__programme", "status")
            .order_by("student__last_name", "student__first_name")
        )


class ShowTestResults(RedirectView):
    """Redirect to a more specialised view for handling the test results for different cases."""

    superuser_view = ShowAllTestResultsViiew
    staff_view = ShowTutorTestResultsViiew

    def get_logged_in_view(self, request):
        """Patch in the kwargs with the user number."""
        self.kwargs["username"] = request.user.username
        self.kwargs["selected_tab"] = "#tests"
        return StudentSummaryView


class GenerateModuleMarksheetView(IsSuperuserViewMixin, FormView):
    """Handles uploading the full Gtradebook."""

    template_name = "minerva/generate_marksheet.html"
    form_class = ModuleSelectForm
    success_url = "/minerva/generate_marksheet/"

    def form_valid(self, form):
        """Respond with a marksheet for the selected module."""
        module = form.cleaned_data["module"]
        return module.generate_marksheet()


class TestDetailView(IsStudentViewixin, DetailView):
    """Provide a detail view for a single test."""

    template_name = "minerva/test-detail.html"
    slug_field = "pk"
    slug_url_kwarg = "pk"
    model = Test
    context_object_name = "test"

    def get_context_data(self, **kwargs):
        """Get plots as extra context data."""
        context = super().get_context_data(**kwargs)
        context["plot1"], context["plot2"] = self._make_plots(context["test"])
        return context

    def _make_plots(self, test):
        """Make the figure for a Test's plots."""
        fig1, pie = plt.subplots(figsize=(3.5, 3.5))
        fig2, hist = plt.subplots(figsize=(4, 3.5))
        data = test.stats
        colours = ["green", "red", "dimgrey", "black"]
        _, texts = pie.pie(list(data.values()), labels=list(data.keys()), colors=colours, labeldistance=0.3)
        for text in texts:
            text.set_bbox({"facecolor": (1, 1, 1, 0.75), "edgecolor": (1, 1, 1, 0.25)})
        with plot_context("seaborn-v0_8-bright"):
            counts, _, _ = hist.hist(
                test.scores, bins=np.linspace(0.0, test.score_possible, int(min(test.score_possible, 21)))
            )
            if counts.size > 0:
                ymin, ymax = 0, counts.max() + 1
            else:
                ymin, ymax = 0, 1
            hist.add_patch(Rectangle((0, ymin), test.passing_score, ymax, facecolor=(0, 0, 0, 0.25)))
            plt.ylim(ymin, ymax)
            hist.set_xlabel("Score")
            hist.set_ylabel("Number of students")
            plt.xlim(0, test.score_possible)
        plt.tight_layout()
        alt1 = f"{test.name} Pass/Faile" + " ".join([f"{label}:{count}" for label, count in data.items()])
        alt2 = f"{test.name} Results" + " ".join([f"{label}:{count}" for label, count in data.items()])
        plt.close("all")
        return ImageData(svg_data(fig1, base64=True), alt1), ImageData(svg_data(fig2, base64=True), alt2)


class ModuleAutocomplete(autocomplete.Select2QuerySetView):
    """Class for autocomplete on module titles."""

    def get_queryset(self):
        """If authenticated, get the list of modules."""
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Module.objects.none()

        qs = Module.objects.all()

        if self.q:
            qs = qs.filter(Q(name__icontains=self.q) | Q(code__icontains=self.q))

        return qs.order_by("code")


class TestAutocomplete(autocomplete.Select2QuerySetView):
    """Class for autocomplete on module titles."""

    def get_queryset(self):
        """If authenticated, get the list of modules."""
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Test.objects.none()

        qs = Test.objects.all()

        if self.q:
            qs = qs.filter(Q(name__icontains=self.q) | Q(description__icontains=self.q))

        return qs.order_by("module__code", "release_date")


class TestResultsBarChartView(IsStaffViewMixin, FormView):
    """Most of the machinery to show a table of student test results."""

    form_class = ModuleSelectPlusForm
    template_name = "minerva/test_barchart.html"

    def __init__(self, *args, **kargs):
        """Construct instance variables."""
        self.module = None
        self.mode = "scor3e"
        self.type = "homework"
        self.tests = []
        super().__init__(*args, **kargs)

    def form_valid(self, form):
        """Update self.module with the module selected in the form."""
        self.module = form.cleaned_data["module"]
        self.mode = form.cleaned_data.get("mode", "score")
        self.type = form.cleaned_data.get("type", "homework")
        if self.module is not None:
            self.tests = self.module.tests.filter(type=self.type).order_by("release_date", "name")
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        """Get the cohort into context from the slug."""
        context = super().get_context_data(**kwargs)
        context["module"] = self.module
        if self.tests:
            context["plot"] = self._make_plot()
        return context

    def _make_plot(self):
        """Make a barchart from the stats for each test in the module."""
        rows = []
        for test in self.tests:
            row = test.stats
            row["name"] = shorten(test.name, width=30)
            rows.append(row)
        df = pd.DataFrame(rows).set_index("name")
        ax = df.plot(
            kind="bar",
            stacked=True,
            color={"Passed": "g", "Failed": "r", "Waiting": "dimgrey", "Not Attempted": "black", "": "white"},
        )
        ax.set_xlabel = ""
        ax.set_ylabel("# Students")
        ax.legend(ncol=5)
        fig = ax.figure
        plt.close("all")
        return ImageData(svg_data(fig, base64=True), alt=f"Summary pass/fail for all {self.type}")
