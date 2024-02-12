# Python imports
import re
from traceback import format_exc
from textwrap import shorten
# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.forms import ValidationError
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.views.generic import FormView

# external imports
import numpy as np
import pandas as pd
from accounts.models import Account
from django_tables2 import SingleTableMixin
from django_tables2.columns import Column
from django_tables2.tables import Table
from pytz import timezone
from util.views import IsSuperuserViewMixin

# app imports
from .forms import ModuleSelectForm, TestImportForm
from .models import ModuleEnrollment, Test, Test_Attempt, Test_Score

TZ = timezone(settings.TIME_ZONE)


# Create your views here.
class ImportTestsView(IsSuperuserViewMixin, FormView):
    """Handles uploading the full Gtradebook."""

    template_name = "minerva/import_tests.html"
    form_class = TestImportForm
    success_url = "/minerva/import_tests/"
    data = []

    test_name = re.compile("(?P<name>.*)\s\[Total\ Pts\:\s(?P<total>[0-9\.]+)\sScore\]\s\|(?P<test_id>.*)")

    def post(self, request, *args, **kwargs):
        """Handle form posting with cutsom work around exceoptions."""
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
                        df = pd.read_csv(f.temporary_file_path())
                    df = df.set_index("Student ID")
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
        results = []
        module = form.cleaned_data["module"]
        for df in self.data:
            ret = {"file": df.filename, "cols": []}
            for col in df.columns:
                if match := self.test_name.search(col):
                    name = match.groupdict()["name"]
                    test_id = match.groupdict()["test_id"]
                    possible = float(match.groupdict()["total"])
                    test, new = Test.objects.get_or_create(test_id=test_id, module=module)
                    if new:
                        ret["cols"].append(f"Saving new test {name} {possible=} {test_id=}")
                        test.name = name
                        test.score_possible = possible
                        test.passing_score = 0.8 * possible
                        test.save()
                    else:
                        test.name = name
                        test.score_possible = possible
                        test.passing_score = 0.8 * possible
                        test.save()

                        ret["cols"].append(f"Found existing column {name} {test_id=}")
                else:
                    ret["cols"].append(f"Unmatched column name {col}")
            results.append(ret)
        context = self.get_context_data()
        context["results"] = results
        return TemplateResponse(self.request, self.template_name, context=context)


class ImportTestHistoryView(IsSuperuserViewMixin, FormView):
    """Handles uploading the Gradebook Hisotry Files."""

    template_name = "minerva/import_history.html"
    form_class = TestImportForm
    success_url = "/minerva/import_history/"
    data = []

    def post(self, request, *args, **kwargs):
        """Handle form posting with cutsom work around exceoptions."""
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
                        df = pd.read_csv(f.temporary_file_path())
                    df.filename = f
                    self.data.append(df)
            except AssertionError:
                raise
            except Exception as e:
                form.add_error(
                    None,
                    f"Could not read Gradebook History  file due to: {e} with {f.temporary_file_path()} {format_exc()}",
                )
                return self.form_invalid(form)
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Process the uploaded test hisotry data."""
        results = []
        module = form.cleaned_data["module"]
        for df in self.data:
            df.Date = pd.to_datetime(df.Date)
            df["AttemptDate"] = pd.to_datetime(df["Attempt Activity"])
            df["AttemptDate"] = df.AttemptDate.apply(TZ.localize)
            df["Date"] = df.Date.apply(TZ.localize)
            ret = {"file": df.filename, "rows": []}
            for _, row in df.iterrows():
                row_report = {} | row.to_dict()
                try:
                    student = Account.objects.get(username=row.Username)
                except ObjectDoesNotExist:
                    row_report["message"] = f"Unknown User {row.Username}"
                    ret["rows"].append(row_report)
                    continue
                try:
                    test = Test.objects.get(name=row.Column, module=module)
                except ObjectDoesNotExist:
                    row_report["message"] = "Unknown test {row.Column}"
                    ret["rows"].append(row_report)
                    continue
                test_score, new = Test_Score.objects.get_or_create(user=student, test=test)
                new_id = f"{row.Column}:{row.Username}:{row.AttemptDate}"
                test_attempt, new = Test_Attempt.objects.get_or_create(
                    attempt_id=new_id, test_entry=test_score, attempted=row.AttemptDate
                )
                if (
                    not new
                    and test_attempt.score is not None
                    and not np.isnan(test_attempt.score)
                    and np.isnan(row.Value)
                ):
                    continue  # Skip over duplicate attempts where the score is NaN
                test_attempt.score = row.Value
                test_attempt.modified = row.Date
                row_report["message"] = (
                    f"Attempt {row.Column} for {row.Username} at {row.AttemptDate} saved with score {row.Value}"
                )
                ret["rows"].append(row_report)
                test_attempt.save()
            results.append(ret)
        context = self.get_context_data()
        context["results"] = results
        return TemplateResponse(self.request, self.template_name, context=context)


class BaseTable(Table):
    """Provides a table with columns for student name, number, programme and status code as per marksheets."""

    class Meta:
        attrs = {"width": "100%"}
        template_name = "django_tables2/bootstrap5.html"
        orderable  = False

    student = Column(orderable  = False)
    number = Column(orderable  = False)
    programme = Column(orderable  = False)
    status = Column(attrs={"th": {"class": "vertical"}},orderable  = False)


class TestResultColumn(Column):
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
            case {"score": score, "passed": passed, "attempt_count": attempts}:
                if attempts > 1:
                    attempts = (
                        '<span class="position-absolute top-0 start-100 translate-middle p-2'
                        + 'bg-warning border border-light rounded-circle">'
                        + '<span class="visually-hidden">Too Many attempts</span>'
                    )
                else:
                    attempts = ""
                if passed:
                    ret = f'<span class="badge bg-success">{score:.1f}{attempts}</span>'
                elif np.isnan(score):
                    ret = f'<span class="badge bg-primary">{score:.1f}{attempts}</span>'
                else:
                    ret = f'<span class="badge bg-danger">{score:.1f}{attempts}</span>'
            case _:
                ret = value

        return format_html(ret)


class ShowTestResults(IsSuperuserViewMixin, SingleTableMixin, FormView):
    """View to show test results for a module in a table."""

    form_class = ModuleSelectForm
    table_class = BaseTable
    template_name = "minerva/test_results.html"
    context_table_name = "test_results"
    table_pagination = False

    def __init__(self, *args, **kargs):
        """Setup instance variables."""
        self.module = None
        self.tests = []
        super().__init__(*args, **kargs)

    def form_valid(self, form):
        """Update self.module with the module selected in the form."""
        self.module = form.cleaned_data["module"]
        if self.module is not None:
            self.tests = self.module.tests.all().order_by("name")
        return self.render_to_response(self.get_context_data())

    def get_table_class(self):
        """Construct the django-tables2 table class for this view."""
        attrs = {}
        for test in self.tests:
            attrs[shorten(test.name, width=30)] = TestResultColumn(orderable  = False)
        klass = type("DynamicTable", (self.table_class,), attrs)
        return klass

    def get_context_data(self, **kwargs):
        """Get the cohort into context from the slug."""
        context = super().get_context_data(**kwargs)
        context["module"]=self.module
        return context

    def get_table_data(self):
        """Fill out the table with data, creating the entries for the MarkType columns to interpret."""
        table = []
        entries = (
            ModuleEnrollment.objects.filter(module=self.module)
            .prefetch_related("student", "student__test_results", "student__programme", "status")
            .order_by("student__last_name", "student__first_name")
        )

        for entry in entries:
            record = {  # Standard student information entries
                "student": entry.student.display_name,
                "number": entry.student.number,
                "programme": entry.student.programme.name,
                "status": entry.status.code,
            }
            for test in self.tests:  # Add columns for the tests
                try:
                    ent = entry.student.test_results.get(test=test)
                    record[shorten(test.name, width=30)] = {x: getattr(ent, x) for x in ["score", "passed", "attempt_count"]}
                except ObjectDoesNotExist:
                    record[test.name] = None

            table.append(record)
        return table

    def get_queryset(self):
        """Use get_table_data instead of a queryset."""
        return self.get_table_data()

class GenerateModuleMarksheetView(IsSuperuserViewMixin, FormView):
    """Handles uploading the full Gtradebook."""

    template_name = "minerva/generate_marksheet.html"
    form_class = ModuleSelectForm
    success_url = "/minerva/generate_marksheet/"


    def form_valid(self,form):
        """Repsond with a marksheet for the selected module."""
        module = form.cleaned_data["module"]
        return module.generate_marksheet()
        