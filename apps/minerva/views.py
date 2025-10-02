"""View classes for the app that handles Minerva integration."""

# Python imports
import csv
import io
import re
from collections import namedtuple
from textwrap import shorten
from traceback import format_exc

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import OuterRef, Q, Subquery
from django.db.utils import IntegrityError
from django.forms import ValidationError
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.html import format_html
from django.views.generic import DetailView, FormView

# external imports
import numpy as np
import pandas as pd
from accounts.models import Account
from accounts.views import StudentSummaryView
from dal import autocomplete
from django_tables2 import SingleTableMixin
from django_tables2.columns import Column
from django_tables2.paginators import LazyPaginator
from htmx_views.views import HTMXProcessMixin
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.style import context as plot_context
from pytz import timezone
from util.http import svg_data
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
    ModuleSelectPlotForm,
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


def set_name(name):
    return shorten(name, width=30, placeholder="[-]").replace(".", "")


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
        self.module = form.cleaned_data["module"]
        response = StreamingHttpResponse(iter(self.response_generator()))
        response["Content-Type"] = "text/plain"
        return response

    def response_generator(self):
        """Yield rows for a table."""
        module = self.form.cleaned_data["module"]
        alt = False
        tests = {}
        for df in self.data:
            for col in df.columns:
                if match := self.test_name.search(col):
                    try:
                        cls = "light" if not alt else "secondary"
                        name = match.groupdict()["name"]
                        test_id = match.groupdict()["test_id"]
                        possible = float(match.groupdict()["total"])
                        yield f"<tr class='tb-{cls}'><td>Matched column: {name} ({test_id})_ for {possible}</td></tr>"
                        try:
                            existing = Test.objects.get(module=module, name=name)
                            test_id = existing.test_id
                            yield "<tr><td>Updating ID</td></tr>"
                        except Test.DoesNotExist:
                            pass
                        try:
                            test = Test.objects.get(test_id=test_id, module=module)
                            new = False
                        except Test.DoesNotExist:
                            test = Test(test_id=test_id, module=module, name=name)
                            test.save()
                            new = True
                        alt = not alt
                        if new:
                            test.name = name
                            test.score_possible = possible
                            test.passing_score = 0.8 * possible
                            test.save()
                            tests[col] = test
                            yield f"<tr class='tb-{cls}'><td>Saving new test {name} {possible=} {test_id=}</td></tr>"
                        else:
                            test.name = name
                            test.score_possible = possible
                            test.save()
                            tests[col] = test
                    except Exception as e:
                        nl = "\n"
                        yield f"<tr class='tb-warning'><td>Error {e} {format_exc().replace(nl,'<br/>')}</td></tr>"
                else:
                    yield f"<tr class='tb-warning'><td>Unmatched column name {col}</td></tr>"
            for _, row in df.iterrows():
                try:
                    cls = "light" if not alt else "secondary"

                    if row["Availability"] == "No" or np.isnan(row["Student ID"]):
                        yield f"<tr><td>Skipping Row {row}</td?</tr>"
                        continue

                    first_name = row["First Name"]
                    last_name = row["Last Name"]
                    sid = int(row["Student ID"])
                    username = row["Username"]
                    user, new = Account.objects.get_or_create(username=username)
                    user.first_name = first_name
                    user.last_name = last_name
                    user.number = sid
                    user.save()
                    yield f"<tr class='tb-{cls}'>{'Added' if new else 'Updated'} {user.display_name}</td></tr>"
                    ModuleEnrollment.objects.get_or_create(module=self.module, student=user)
                    for mod in self.module.sub_modules.all():
                        ModuleEnrollment.objects.get_or_create(module=mod, student=user)
                    alt = not alt
                    if new:
                        yield f"<tr class='tb-success'><td>New user {user.display_name} created</tr></td>"
                    else:
                        yield f"<tr class='tb-{cls}'><td>Existing user {user.display_name} updated</td></tr>"
                    for col, test in tests.items():
                        cls = "light" if not alt else "secondary"
                        score = row[col]
                        if not isinstance(score, float) or np.isnan(score):
                            yield f"<tr class='tb-{cls}'><td>Skipping Score {score}</td></tr>"
                            continue  # bypass if no score for this student for this test
                        ts, new = Test_Score.objects.get_or_create(user=user, test=test)
                        ta, _ = Test_Attempt.objects.get_or_create(test_entry=ts, score=score)
                        ta.save()
                        ts.save()
                        yield (
                            f"<tr class='tb-{cls}'><td>Test score for {user.display_name} and {test.name}"
                            + " of  {score} {'created' if new else 'updted'}</td></tr>"
                        )
                except Exception as e:
                    yield f"<tr class='tb-warning'><td>Row {e}</td></tr>"


class ImportTestHistoryView(IsSuperuserViewMixin, FormView):
    """Handles uploading the Gradebook Hisotry Files."""

    template_name = "minerva/import_history.html"
    form_class = TestHistoryImportForm
    success_url = "/minerva/import_history/"


class StreamingImportTestsHistoryView(ImportTestHistoryView):
    """Streaming version of the ImportTestHistoryView."""

    def post(self, request, *args, **kwargs):
        """Handle form posting with cutsom work around exceptions."""
        self.data = []
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist("upload_file")
        if form.is_valid():
            if len(files) < 1:
                raise ValidationError("Expecting one or more files.")
            try:
                self.data = []
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
            for _, row in df.iterrows():
                try:
                    try:
                        row.Date = pd.to_datetime(row.Date)
                        if row.Date.tzinfo is None:
                            row.Date = TZ.localize(row.Date)
                        row.AttemptDate = pd.to_datetime(row["Attempt Activity"])

                    except Exception as err:
                        yield f"<tr><td>Time Conversion Error 1{err}</td></tr>"
                        continue
                    try:
                        row.AttemptDate = TZ.localize(row.AttemptDate)
                    except Exception as err:
                        row.AttemptDate = row.Date

                    try:
                        student = Account.objects.get(username=row.Username)
                    except ObjectDoesNotExist:
                        print("Yield")
                        yield f"<tr class='tb-warning'><td>Unknown User {row.Username}</td></tr>"
                        continue
                    try:
                        test = Test.get_by_column_name(row.Column, module=module)
                    except ObjectDoesNotExist:
                        print("Yield")
                        yield f"<tr class='tb-warning'><td>Unknown test {row.Column}</td></tr>"
                        continue

                    test_score, new = Test_Score.objects.get_or_create(user=student, test=test)

                    if (
                        not new
                        and test_score.score is not None
                        and (np.isnan(row.Value) or test_score.score >= row.Value)
                    ):
                        yield (
                            f"<tr class='tb-info'><td>Skipping {student.display_name} for {row.Value} as not "
                            + "substantive change</td></tr>"
                        )
                    new_id = f"{row.Column}:{row.Username}:{row.AttemptDate}"
                    test_attempt, new = Test_Attempt.objects.get_or_create(attempt_id=new_id, test_entry=test_score)
                    if (
                        not new
                        and test_attempt.score is not None
                        and not np.isnan(test_attempt.score)
                        and np.isnan(row.Value)
                    ):
                        yield (
                            f"<tr cl;ass='tb tb-info'><td>Skipping {student.display_name} for existing"
                            + f" score {test_attempt.score} and new score {row.Value}</td></tr>"
                        )
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
                        f"<tr class='tb-{cls}'><td>Attempt {row.Column} for {student.display_name} at {row.AttemptDate}"
                        + f" saved with score {row.Value}</td></tr>"
                    )
                except Exception as e:
                    yield (f"<r class='bg tb-danger'><td>{ e }<br/><pre>{ format_exc() }</pre></td></tr>\n")


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
            if score is None:
                return f'<div class="badge rounded-pil" style="background-color: {bg_color};">&nbsp;!&nbsp;</div>'
            return f'<div class="badge rounded-pil" style="background-color: {bg_color};">{score:.1f}</div>'
        if score is None or np.isnan(score):
            return '<div class="badge rounded-pil" style="background-color: dimgrey;">&nbsp;!&nbsp;</div>'
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


class BaseShowTestResultsView(SingleTableMixin, HTMXProcessMixin, FormView):
    """Most of the machinery to show a table of student test results."""

    form_class = ModuleSelectPlusForm
    table_class = BaseTable
    paginator_class = LazyPaginator
    template_name = "minerva/test_results.html"
    template_name_next_batch = "minerva/parts/test_results_next_batch.html"
    context_table_name = "test_results"
    table_pagination = {"per_page": 10}

    def __init__(self, *args, **kargs):
        """Construct instance variables."""
        self.module = None
        self.mode = "scor3e"
        self.category = None
        self.tests = []
        self._entries = []
        super().__init__(*args, **kargs)

    @property
    def entries(self):
        """Cache entries between metrhods."""
        if len(self._entries) == 0:
            self._entries = self.get_entries()
        return self._entries

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }
        match self.request.method:
            case "POST" | "PUT":
                kwargs.update(
                    {
                        "data": self.request.POST,
                        "files": self.request.FILES,
                    }
                )
            case "GET" if "module" in self.request.GET:
                kwargs.update(
                    {
                        "data": self.request.GET,
                        "files": self.request.FILES,
                    }
                )
            case _:
                pass

        return kwargs

    def form_invalid(self, form):
        """Pick up bad form data."""
        data = form.errors
        return super().form_invalid(form)

    def form_valid(self, form):
        """Update self.module with the module selected in the form."""
        self.module = form.cleaned_data["module"]
        self.mode = form.cleaned_data.get("mode", "score")
        self.category = form.cleaned_data.get("type")
        if self.module is not None:
            self.tests = self.module.tests.filter(category=self.category).order_by("release_date", "name")
        self.page = int(self.request.GET.get("page", 1))
        return self.render_to_response(self.get_context_data())

    def get_table_class(self):
        """Construct the django-tables2 table class for this view."""
        attrs = {}
        for test in self.tests:
            attrs[set_name(test.name)] = TestResultColumn(orderable=False, mode=self.mode, test=test)
        klass = type("DynamicTable", (self.table_class,), attrs)
        setattr(klass._meta, "row_attrs", {"class": "student_link"})
        setattr(klass._meta, "template_name", "util/table.html")
        return klass

    def get_context_data(self, **kwargs):
        """Get the cohort into context from the slug."""
        context = super().get_context_data(**kwargs)
        context["module"] = self.module
        context["category"] = self.category
        return context

    def get_context_data_next_batch(self, **kwargs):
        ret = self.get_context_data(**kwargs)
        return ret

    def get_entries(self):
        """Override to return the data required."""
        raise NotImplementedError("Need to override the get_entries method.")

    def get_table_data(self):
        """Fill out the table with data, creating the entries for the MarkType columns to interpret."""
        tests = {set_name(test.name): test.pk for test in self.tests}
        table = [Row_Dict(student, tests) for student in self.entries]
        return table

    def get_queryset(self):
        """Use get_table_data instead of a queryset."""
        return self.get_table_data()


class Row_Dict:
    """Proxy for a dictionary that delays evaluating the test results."""

    def __init__(self, student, tests):
        self.student = student
        self.test_results = student.test_results.all()
        self.tests = tests

    def __getitem__(self, index):
        match index:
            case "student":
                return self.student
            case "SID" | "number":
                return self.student.number
            case "programme":
                return self.student.programme.name
            case "status":
                return self.student.status
            case test if test in self.tests:
                try:
                    return self.test_results.get(test__pk=self.tests[test])
                except ObjectDoesNotExist:
                    return None
            case _:
                return False


class ShowAllTestResultsViiew(IsSuperuserViewMixin, BaseShowTestResultsView):
    """Show a table of all student test results."""

    def get_entries(self):
        """Get the students to include in the table."""
        if not getattr(self, "page", False):
            return Account.objects.none()
        enroillments = ModuleEnrollment.objects.filter(module=self.module, active=True).values("id")
        status = enroillments.filter(student=OuterRef("pk")).values("status__code")
        qs = (
            Account.objects.filter(module_enrollments__in=enroillments)
            .annotate(status=Subquery(status))
            .select_related("programme")
            .prefetch_related("test_results")
            .order_by("last_name", "first_name")
        )
        return qs


class ShowTutorTestResultsViiew(IsStaffViewMixin, BaseShowTestResultsView):
    """Show a table of student test results for the current user's tutees."""

    def get_entries(self):
        """Get the students to include in the table."""
        enroillments = ModuleEnrollment.objects.filter(module=self.module, active=True).values("id")
        status = enroillments.filter(student=OuterRef("pk")).values("status__code")
        qs = (
            Account.objects.filter(module_enrollments__in=enroillments, tutorial_group__tutor=self.request.user)
            .annotate(status=Subquery(status))
            .select_related("programme")
            .prefetch_related("test_results")
            .order_by("last_name", "first_name")
        )
        return qs


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


class StudentPerformanceSpreadsheetView(IsSuperuserViewMixin, FormView):
    """Make a pandas dataframe of student performance and stream it to the user."""

    template_name = "minerva/generate_performance_spreadheet.html"
    form_class = ModuleSelectForm
    success_url = "/minerva/generate_performance_spreadsheet/"

    def form_valid(self, form):
        """Respond with a marksheet for the selected module."""
        module = form.cleaned_data["module"]
        cols = {
            "Homework Passed": "passed_tests",
            "Home Failed": "failed_tests",
            "Labs Passed": "passed_labs",
            "Labs Failed": "failed_labs",
            "Coding Passed": "passed_coding",
            "Coding Failed": "failed_coding",
            "VITALs passed": "passed_vitals",
            "VITALs failed": "failed_vitals",
            "Required Work": "required_tests",
        }
        rows = []
        for student in module.students.all():
            data = {"Student": student.display_name, "SID": student.number, "Programme": student.programme}
            for col, attr in cols.items():
                data[col] = ",\n".join([str(x) for x in getattr(student, attr).all()])
            rows.append(data)
        df = pd.DataFrame(rows)

        # Create a BytesIO buffer
        output = io.BytesIO()

        # Write Excel file to buffer
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Data")

        # Rewind buffer
        output.seek(0)

        # Create response
        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="' + f"{module.code}_summary.xlsx" + '"'
        return response


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
        try:
            _, texts = pie.pie(list(data.values()), labels=list(data.keys()), colors=colours, labeldistance=0.3)
            for text in texts:
                text.set_bbox({"facecolor": (1, 1, 1, 0.75), "edgecolor": (1, 1, 1, 0.25)})
        except ValueError:
            pass
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

    form_class = ModuleSelectPlotForm
    template_name = "minerva/test_barchart.html"

    def __init__(self, *args, **kargs):
        """Construct instance variables."""
        self.module = None
        self.mode = "scor3e"
        self.category = "homework"
        self.tests = []
        super().__init__(*args, **kargs)

    def form_valid(self, form):
        """Update self.module with the module selected in the form."""
        self.module = form.cleaned_data["module"]
        self.category = form.cleaned_data.get("type")
        if self.module is not None:
            if self.category.text.lower() in ["homework", "lab experiment", "code tasks"]:
                self.tests = self.module.tests.filter(category=self.category).order_by("release_date", "name")
            elif self.category.text.lower() == "vitals":
                m = self.module
                ids = [x.student.pk for x in m.student_enrollments.all()]
                self.tests = (
                    m.VITALS.model.objects.filter(module__student_enrollments__student__pk__in=ids)
                    .distinct()
                    .order_by("start_date")
                )
            elif self.category.text.lower() == "tutorial":
                self.tests = self.module.tutorial_sessions.distinct().order_by("semester", "week")
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
            row["name"] = set_name(test.name)
            rows.append(row)
        df = pd.DataFrame(rows).set_index("name")
        ax = df.plot(
            kind="bar",
            stacked=True,
            color=test.stats_legend,
            figsize=(max(6, self.tests.count() / 5), 6),
        )
        ax.legend(bbox_to_anchor=(0, 1.02, 1, 0.2), loc="lower left", mode="expand", borderaxespad=0, ncol=3)
        ax.set_xlabel(None)
        ax.set_ylabel("# Students")
        fig = ax.figure
        plt.close("all")
        return ImageData(svg_data(fig, base64=True), alt=f"Summary pass/fail for all {self.category.text}")
