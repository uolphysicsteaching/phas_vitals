# -*- coding: utf-8 -*-
"""Forms for the vitals app."""

# Django imports
from django import forms

# external imports
from dal import autocomplete

# app imports
from .models import VITAL, VITAL_Result, VITAL_Test_Map


class VITALForm(forms.ModelForm):

    """Form for referring to VITALs."""

    class Meta:
        model = VITAL
        fields = "__all__"


class VITAL_Test_MapForm(forms.ModelForm):

    """Form for VITAL-Test Mapping Edits."""

    class Meta:
        model = VITAL_Test_Map
        fields = "__all__"
        widgets = {
            "test": autocomplete.ModelSelect2(url="minerva:Test_lookup"),
            "vital": autocomplete.ModelSelect2(url="vitals:VITAL_lookup"),
        }


class VITAL_ResultForm(forms.ModelForm):

    """Form for VITAL-Test Mapping Edits."""

    class Meta:
        model = VITAL_Result
        fields = "__all__"
        widgets = {
            "vital": autocomplete.ModelSelect2(url="vitals:VITAL_lookup"),
        }
