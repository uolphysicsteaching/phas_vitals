# -*- coding: utf-8 -*-
"""Start an import Wizard for Gradescope files."""

# Python imports
import os
import pathlib
from copy import deepcopy
from mimetypes import guess_type

# Django imports
import django.utils.timezone as tz
from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import HttpResponseRedirect

# external imports
import magic
import numpy as np
import pandas as pd
from dateutil import parser
from formtools.wizard.views import SessionWizardView
from minerva.models import Test_Attempt, Test_Score
from util.views import IsStaffViewMixin, get_encoding

# app imports
from .forms import UploadGradecentreForm


def get_mime(content):
    """Get the mime type of the current file as a string.

    if content is None, use self.content as the file."""
    if content is None or not content:
        return ""

    if isinstance(content, (str, pathlib.Path)):
        content = File(open(content, "rb"))
        closeme = True
    else:
        closeme = False

    try:
        with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as mimemagic:
            for chunk in content.chunks():
                mime = mimemagic.id_buffer(chunk)
                break
    except AttributeError:
        mime = guess_type(content.name)[0]
    except TypeError:
        for chunk in content.chunks():
            mime = magic.from_buffer(chunk, mime=True)
            break
    finally:
        if closeme:
            content.close()

    return mime


class ColumnAssignmentForm(forms.Form):
    """A container form to use with formsetfactory to set up column assignments."""


class GradebookImport(IsStaffViewMixin, SessionWizardView):
    """Provide a wizard to import a spreadsheet from Gradecentre."""

    file_storage = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "tmp"))
    forms = [("file", UploadGradecentreForm), ("columns", ColumnAssignmentForm)]
    template_name = "util/gradebook_import.html"

    def construct_form(self, module, df, data, files):
        """Construct a form for mapping the components of module to the columns in data."""
        force_cols = [(x, x) for x in list(df.columns)]
        sid_guess = self._find_column(force_cols, "student id")
        date_guess = self._find_column(force_cols, "attempt")

        step = "columns"

        class ColumnAssignmentForm(forms.Form):
            """A container form to use with formsetfactory to set up column assignments."""

        form_class = ColumnAssignmentForm
        kwargs = self.get_form_kwargs(step)
        kwargs.update(
            {
                "data": data,
                "files": files,
                "prefix": self.get_form_prefix(step, form_class),
                "initial": self.get_form_initial(step),
            }
        )

        columns = [("", "None")] + force_cols
        self._add_choice_field(form_class, "studentID", force_cols, "Student ID Column", sid_guess)
        self._add_choice_field(
            form_class, "date", [("", "None")] + force_cols, "Date Column", date_guess, required=False
        )
        cols = module.tests.all().order_by("release_date")
        for test in module.tests.all().order_by("release_date"):
            self._add_choice_field(form_class, test.name, columns, f"Test: {test.name}", required=False)

        return form_class(**kwargs)

    def get_form(self, step=None, data=None, files=None):
        """For the final step we have an instance already."""
        step = step or self.steps.current
        if step == "columns":
            module = self.get_cleaned_data_for_step("file")["module"]
            fname = self.get_cleaned_data_for_step("file")["gradecentre"]._name
            mime_type = get_mime(os.path.join(settings.MEDIA_ROOT, "tmp", fname))
            match mime_type:
                case "text/csv":
                    enc = get_encoding(os.path.join(settings.MEDIA_ROOT, "tmp", fname))
                    df = pd.read_csv(os.path.join(settings.MEDIA_ROOT, "tmp", fname), encoding=enc["encoding"])
                case "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                    df = pd.read_excel(os.path.join(settings.MEDIA_ROOT, "tmp", fname))
                case _:
                    raise ValueError(f"Unsupported gradecentre MIME type: {mime_type}")
            return self.construct_form(module, df, data, files)
        else:
            return super().get_form(step, data, files)

    def done(self, form_list, **kwargs):
        """Do the actual import operation."""
        fname = self.get_cleaned_data_for_step("file")["gradecentre"]._name
        fname = os.path.join(settings.MEDIA_ROOT, "tmp", fname)
        mime_type = get_mime(fname)
        match mime_type:
            case "text/csv":
                df = pd.read_csv(fname)
            case "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                df = pd.read_excel(fname)
        module = self.get_cleaned_data_for_step("file")["module"]

        cols = self.get_cleaned_data_for_step("columns")
        studentID_col, date_col, mapping = self._extract_columns(cols, module)

        df = df.set_index(studentID_col)
        self._process_rows(df, module, mapping, date_col)

        os.unlink(fname)
        return HttpResponseRedirect("/util/tools/")

    def _find_column(self, columns, keyword):
        """Locate a column within the keywords."""
        for col in columns:
            if keyword in col[0].lower():
                return col
        return columns[0]

    def _add_choice_field(self, form_class, name, choices, label, initial=None, required=True):
        """Add choice field to the form."""
        form_class.base_fields[name] = forms.ChoiceField(
            choices=choices, label=label, initial=initial, required=required
        )

    def _extract_columns(self, cols, module):
        """Try to match columns to tests or SID column."""
        mapping = {}
        studentID_col = date_col = None

        for field, col in cols.items():
            if field == "studentID":
                studentID_col = col
            elif field == "date":
                date_col = col
            elif col:
                try:
                    test = module.tests.all().get(name=field)
                    mapping[col] = test
                except ObjectDoesNotExist:
                    pass

        return studentID_col, date_col, mapping

    def _process_rows(self, df, module, mapping, date_col):
        """Process spreadsheet results with bulk lookups and writes."""
        return self._bulk_process_attempts(df, module, mapping, date_col)

    @staticmethod
    @transaction.atomic
    def _bulk_process_attempts(df, module, mapping, date_col):
        """Filter relevant cells, then write attempts in database-sized batches."""
        if not mapping or df.empty:
            return {"rows": len(df), "attempts": 0, "students": 0, "scores": 0}

        # Reduce the dataframe to mapped result columns before expanding it.
        # This avoids spending time on the many unrelated Gradebook columns.
        result_columns = list(mapping)
        data = df.loc[:, result_columns].copy()
        data["student_number"] = pd.to_numeric(df.index, errors="coerce")
        if date_col:
            dates = pd.to_datetime(df[date_col], errors="coerce")
            if getattr(dates.dt, "tz", None) is None:
                dates = dates.dt.tz_localize(settings.TIME_ZONE, ambiguous="NaT", nonexistent="shift_forward")
            else:
                dates = dates.dt.tz_convert(settings.TIME_ZONE)
            data["attempted"] = dates
        else:
            data["attempted"] = tz.now()

        # Convert the selected mark columns in one operation and discard blanks,
        # invalid student IDs and invalid marks before touching the database.
        long_data = data.melt(
            id_vars=["student_number", "attempted"],
            value_vars=result_columns,
            var_name="result_column",
            value_name="mark",
        )
        long_data["mark"] = pd.to_numeric(long_data["mark"], errors="coerce")
        long_data = long_data.dropna(subset=["student_number", "mark"])
        if long_data.empty:
            return {"rows": len(df), "attempts": 0, "students": 0, "scores": 0}

        student_numbers = set(long_data["student_number"].astype(int))
        enrollments = module.student_enrollments.filter(student__number__in=student_numbers).select_related("student")
        students = {enrollment.student.number: enrollment.student for enrollment in enrollments}
        long_data["student_number"] = long_data["student_number"].astype(int)
        long_data = long_data[long_data["student_number"].isin(students)]
        if long_data.empty:
            return {"rows": len(df), "attempts": 0, "students": 0, "scores": 0}

        pairs = {(students[row.student_number].pk, mapping[row.result_column].pk) for row in long_data.itertuples()}
        user_ids = {user_id for user_id, _ in pairs}
        test_ids = {test_id for _, test_id in pairs}
        score_map = {
            (score.user_id, score.test_id): score
            for score in Test_Score.objects.filter(user_id__in=user_ids, test_id__in=test_ids)
        }
        Test_Score.objects.bulk_create(
            [
                Test_Score(user_id=user_id, test_id=test_id)
                for user_id, test_id in pairs
                if (user_id, test_id) not in score_map
            ],
            ignore_conflicts=True,
        )
        score_map = {
            (score.user_id, score.test_id): score
            for score in Test_Score.objects.filter(user_id__in=user_ids, test_id__in=test_ids)
        }

        now = tz.now()
        pending = {}
        for row in long_data.itertuples():
            student = students[row.student_number]
            test = mapping[row.result_column]
            attempted = row.attempted
            if pd.isna(attempted):
                attempted = now
            attempt_id = f"{test.test_id}_{student.number}_{attempted.strftime('%Y%m%d')}_{row.mark}"
            pending[attempt_id] = (score_map[(student.pk, test.pk)], float(row.mark), attempted)

        existing = Test_Attempt.objects.in_bulk(pending, field_name="attempt_id")
        created = []
        updated = []
        for attempt_id, (score, mark, attempted) in pending.items():
            attempt = existing.get(attempt_id)
            if attempt is None:
                attempt = Test_Attempt(
                    attempt_id=attempt_id,
                    test_entry=score,
                    created=now,
                )
                created.append(attempt)
            else:
                updated.append(attempt)
            attempt.score = mark
            attempt.attempted = attempted
            attempt.modified = now

        Test_Attempt.objects.bulk_create(created)
        Test_Attempt.objects.bulk_update(updated, ["score", "attempted", "modified"])

        # Test_Attempt.save() normally recalculates its parent on every cell.
        # Once all attempts exist, one save per affected score is sufficient.
        affected_score_ids = {score.pk for score, _, _ in pending.values()}
        for score in Test_Score.objects.filter(pk__in=affected_score_ids).select_related("test", "user"):
            score.save()

        return {
            "rows": len(df),
            "attempts": len(pending),
            "students": len({score.user_id for score, _, _ in pending.values()}),
            "scores": len(affected_score_ids),
        }

    def _parse_date(self, row, date_col):
        """Parse the date for importing test results."""
        if date_col:
            date = row[date_col]
            if isinstance(date, str) and date:
                return parser.parse(date)
        return None

    def _process_attempts(self, row, student, mapping, date):
        """Process a single attempt from a row."""
        for testname, test in mapping.items():
            try:
                mark = float(row[testname])
            except (TypeError, ValueError):
                continue
            if not np.isnan(mark):
                test.add_attempt(student, mark, date)
