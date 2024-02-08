import pandas as pd
from traceback import format_exc
import re
from pytz import timezone


# Django imports
from django.conf import settings

from django.template.response import TemplateResponse

from util.views import IsSuperuserViewMixin
from django.views.generic import FormView
from django.forms import ValidationError
from django.core.exceptions import ObjectDoesNotExist

from accounts.models import Account

from .models import Test, Test_Score, Test_Attempt
from .forms import TestImportForm

TZ=timezone(settings.TIME_ZONE)

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
            df["Date"]=df.Date.apply(TZ.localize)
            ret = {"file": df.filename, "rows": []}
            for _, row in df.iterrows():
                row_report = {} | row.to_dict()
                try:
                    student = Account.objects.get(username=row.Username)
                except ObjectDoesNotExist:
                    row_report["message"] = f"Unknown User {row.Username}"
                try:
                    test = Test.objects.get(name=row.Column, module=module)
                except ObjectDoesNotExist:
                    row_report["message"] = "Unknow test {row.Column}"
                test_score, new = Test_Score.objects.get_or_create(user=student, test=test)
                if new:
                    test_score.save()
                new_id = f"{row.Column}:{row.Username}:{row.AttemptDate}"
                test_attempt, new = Test_Attempt.objects.get_or_create(
                    attempt_id=new_id, test_entry=test_score, attempted=row.AttemptDate
                )
                test_attempt.score = row.Value
                test_attempt.modified = row.Date
                row_report[
                    "message"
                ] = f"Attempt {row.Column} for {row.Username} at {row.AttemptDate} saved with score {row.Value}"
                ret["rows"].append(row_report)
                di=test_attempt.__dict__
                test_attempt.save()
            results.append(ret)
        context = self.get_context_data()
        context["results"] = results
        return TemplateResponse(self.request, self.template_name, context=context)
