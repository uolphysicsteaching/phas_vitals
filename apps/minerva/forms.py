# -*- coding: utf-8 -*-
"""Forms for the minerva interacting application."""
# Django imports
from django import forms
from django.db.models import Count, Q
from django.forms.widgets import Select

# external imports
from dal import autocomplete
from util.forms import get_mime

# app imports
from .models import GradebookColumn, Module, Test, Test_Score


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

        if content is None, use self.content as the file.
        """
        return get_mime(content)


class TestHistoryImportForm(forms.Form):
    """Form that is for uploading the Gradebook History Log."""

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

        if content is None, use self.content as the file.
        """
        return get_mime(content)


HAS_VITALS = Q(vitals_count__gt=0)
HAS_SUBMODS = Q(sub_mods_count__gt=0)


class ModuleSelectForm(forms.Form):
    """Form that selects a module and immediately updates."""

    module = forms.ModelChoiceField(
        required=False,
        queryset=Module.objects.annotate(vitals_count=Count("VITALS"), sub_mods_count=Count("sub_modules")).filter(
            HAS_VITALS | HAS_SUBMODS
        ),
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )


class VITALsModuleSelectForm(forms.Form):
    """Form that selects a module and immediately updates."""

    module = forms.ModelChoiceField(
        required=False,
        queryset=Module.objects.annotate(vitals_count=Count("VITALS"), sub_mods_count=Count("sub_modules")).filter(
            HAS_VITALS
        ),
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )


class AssessmentModuleSelectForm(forms.Form):
    """Form that selects a module and immediately updates."""

    module = forms.ModelChoiceField(
        required=False,
        queryset=Module.objects.annotate(vitals_count=Count("VITALS"), sub_mods_count=Count("sub_modules")).filter(
            HAS_SUBMODS
        ),
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

    type = forms.ChoiceField(
        choices=Test.TEST_TYPES,
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )


class ModuleSelectPlotForm(forms.Form):
    """Form that selects a module and view type and then updates."""

    module = forms.ModelChoiceField(
        required=False,
        queryset=Module.objects.annotate(tests_count=Count("tests")).filter(tests_count__gt=0),
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )

    type = forms.ChoiceField(
        choices=Test.TEST_TYPES + [("vitals", "VITALs"), ("engagement", "Tutorial Attendance")],
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )


class Test_ScoreForm(forms.ModelForm):
    """Form with lookup for Test and student fields."""

    class Meta:
        model = Test_Score
        fields = "__all__"
        widgets = {
            "test": autocomplete.ModelSelect2(url="minerva:Test_lookup"),
            "user": autocomplete.ModelSelect2(url="accounts:Student_lookup"),
        }


class GradebookColumnForm(forms.ModelForm):
    """Form with lookup for Test field for admining Gradebook columns."""

    class Meta:
        model = GradebookColumn
        fields = "__all__"
        widgets = {
            "test": autocomplete.ModelSelect2(url="minerva:Test_lookup"),
        }
