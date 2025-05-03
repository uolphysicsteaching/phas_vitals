# -*- coding: utf-8 -*-
"""Start an import Wizard for Gradescope files."""

# Python imports
import os
from copy import deepcopy

# Django imports
import django.utils.timezone as tz
from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponseRedirect

# external imports
import numpy as np
import pandas as pd
from dateutil import parser
from formtools.wizard.views import SessionWizardView
from util.views import IsStaffViewMixin, get_encoding

# app imports
from .forms import UploadGradecentreForm


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
        form_class = deepcopy(ColumnAssignmentForm)
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

        for test in module.tests.all().order_by("release_date"):
            self._add_choice_field(form_class, test.name, columns, f"Test: {test.name}", required=False)

        return form_class(**kwargs)

    def get_form(self, step=None, data=None, files=None):
        """For the final step we have an instance already."""
        step = step or self.steps.current
        if step == "columns":
            module = self.get_cleaned_data_for_step("file")["module"]
            fname = self.get_cleaned_data_for_step("file")["gradecentre"]._name
            enc = get_encoding(os.path.join(settings.MEDIA_ROOT, "tmp", fname))
            df = pd.read_csv(os.path.join(settings.MEDIA_ROOT, "tmp", fname), encoding=enc["encoding"])
            return self.construct_form(module, df, data, files)
        else:
            return super().get_form(step, data, files)

    def done(self, form_list, **kwargs):
        """Do the actual import operation."""
        fname = self.get_cleaned_data_for_step("file")["gradecentre"]._name
        fname = os.path.join(settings.MEDIA_ROOT, "tmp", fname)
        df = pd.read_csv(fname)
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
        """Process a single row of the spreadsheet."""
        for sid, row in df.iterrows():
            if np.isnan(sid):
                continue
            try:
                student = module.student_enrollments.get(student__number=sid).student
            except ObjectDoesNotExist:
                continue
            if date_col is None:
                date = tz.today()
            else:
                date = self._parse_date(row, date_col)
            self._process_attempts(row, student, mapping, date)

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
