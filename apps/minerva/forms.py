# -*- coding: utf-8 -*-
"""
Created on Tue Feb  6 14:33:54 2024

@author: gavin
"""
# Django imports
from django import forms
from django.forms.widgets import Select

# external imports
from util.forms import get_mime

# app imports
from .models import Module


class TestImportForm(forms.Form):

    module = forms.ModelChoiceField(queryset=Module.objects.all())

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
        content = self.cleaned_data.get("upload_file", False)
        filetype = self.get_mime(content)
        if filetype and filetype not in self._pass_files:
            raise forms.ValidationError("File is not a valid type {} not in {}".format(filetype, ",".join(self._pass_files)))
        return content

    @classmethod
    def get_mime(cls, content):
        """Get the mime type of the current file as a string.

        if content is None, use self.content as the file."""

        return get_mime(content)

class ModuleSelectForm(forms.Form):

    module = forms.ModelChoiceField(
        required=False, queryset=Module.objects.all(), widget=Select(attrs={"onChange": "this.form.submit();"})
    )
