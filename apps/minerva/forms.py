# -*- coding: utf-8 -*-
"""Forms for the minerva interacing application."""
# Django imports
from django import forms
from django.db.models import Count
from django.forms.widgets import Select

# external imports
from util.forms import get_mime

# app imports
from .models import Module


class TestImportForm(forms.Form):
    """Form used to select a module and upload file for importing Full Gradbooks from Minerva."""

    module = forms.ModelChoiceField(queryset=Module.objects.all())

    _pass_files = [  # TODO add code into the view to automatically adapt to these accepted file formats.
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
        "text/csv",
        "application/zip",
        "application/csv",
        "text/plain",
    ]

    upload_file = forms.FileField()

    def clean_spreadsheet(self):
        """Make sure the file mimetype and extension look ok."""
        content = self.cleaned_data.get("upload_file", False)
        filetype = self.get_mime(content)
        if filetype and filetype not in self._pass_files:
            raise forms.ValidationError(
                "File is not a valid type {} not in {}".format(filetype, ",".join(self._pass_files))
            )
        return content

    @classmethod
    def get_mime(cls, content):
        """Get the mime type of the current file as a string.

        if content is None, use self.content as the file."""

        return get_mime(content)


class TestHistoryImportForm(forms.Form):
    """This version of the fomr is for uploading the Gradebook History Log."""

    module = forms.ModelChoiceField(
        queryset=Module.objects.annotate(tests_count=Count("tests")).filter(tests_count__gt=0)
    )

    _pass_files = [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
        "text/csv",
        "application/zip",
        "application/csv",
        "text/plain",
    ]

    upload_file = forms.FileField()

    def clean_spreadsheet(self):
        """Check the mime-type and extension to make sure we like this file."""
        content = self.cleaned_data.get("upload_file", False)
        filetype = self.get_mime(content)
        if filetype and filetype not in self._pass_files:
            raise forms.ValidationError(
                "File is not a valid type {} not in {}".format(filetype, ",".join(self._pass_files))
            )
        return content

    @classmethod
    def get_mime(cls, content):
        """Get the mime type of the current file as a string.

        if content is None, use self.content as the file."""

        return get_mime(content)


class ModuleSelectForm(forms.Form):
    """Form that selects a module and immediately updates."""

    module = forms.ModelChoiceField(
        required=False,
        queryset=Module.objects.annotate(vitals_count=Count("VITALS")).filter(vitals_count__gt=0),
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )


class ModuleSelectPlusForm(forms.Form):
    """Form that sel4ects a module and view mode and then updates."""

    module = forms.ModelChoiceField(
        required=False,
        queryset=Module.objects.annotate(tests_count=Count("tests")).filter(tests_count__gt=0),
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )

    mode = forms.ChoiceField(
        choices=[("score", "Test Scores"), ("attempts", "Test Attempts")],
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )
