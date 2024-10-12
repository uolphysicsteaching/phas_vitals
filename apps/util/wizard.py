# -*- coding: utf-8 -*-
"""
Start an import Wizard for Gradescope files
"""
# Python imports
import os
from copy import deepcopy

# Django imports
from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import FileSystemStorage
from django.db.models import Count
from django.http import HttpResponseRedirect

# external imports
import numpy as np
import pandas as pd
from dateutil import parser
from formtools.wizard.views import SessionWizardView
from minerva.models import Module, Test
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
        """Construct a form for mapping the compoinents of module to the columns in data."""
        force_cols = [(x, x) for x in list(df.columns)]
        for col in force_cols:
            if "student id" in col[0].lower():
                break
        sid_guess = col
        for col in force_cols:
            if "attempt" in col[0].lower():
                break
        date_guess = col
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
        form_class.base_fields["studentID"] = forms.ChoiceField(
            choices=force_cols, label="Student ID Column", initial=sid_guess, required=True
        )
        form_class.base_fields["date"] = forms.ChoiceField(
            choices=force_cols, label="Date Column", initial=date_guess, required=False
        )
        for test in module.tests.all().order_by("release_date"):
            form_class.base_fields[test.name] = forms.ChoiceField(
                choices=columns, label=f"Test: {test.name}", initial="", required=False
            )
        return form_class(**kwargs)

    def get_form(self, step=None, data=None, files=None):
        """For the final step we have an instance already."""
        if step is None:
            step = self.steps.current
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
        mapping = {}
        date_col = None
        for field, col in cols.items():
            if field == "studentID":
                studentID_col = col
                continue
            if field == "date":
                date_col = col
                continue
            if col == "":
                continue
            try:
                test = module.tests.all().get(name=field)
            except ObjectDoesNotExist:
                continue
            mapping[col] = test

        df = df.set_index(studentID_col)

        for sid, row in df.iterrows():
            if np.isnan(sid):
                continue
            try:
                student = module.student_enrollments.get(student__number=sid).student
            except ObjectDoesNotExist:
                continue
            if date_col:
                date = row[date_col]
                if isinstance(date, str) and date:
                    date = parser.parse(date)
            else:
                date = None
            for testname, test in mapping.items():
                try:
                    mark = float(row[testname])
                except (TypeError, ValueError):
                    continue
                if np.isnan(mark):
                    continue
                test.add_attempt(student, mark, date)

        os.unlink(fname)

        return HttpResponseRedirect(f"/util/tools/")
