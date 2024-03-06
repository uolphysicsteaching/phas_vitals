# -*- coding: utf-8 -*-
# Django imports
from django import forms
from django.db.models import Count, Q
from django.forms.widgets import Select

# app imports
from .models import Account, Cohort, academic_Q, students_Q


class StudentSelectForm(forms.Form):
    """A form to select students with."""

    user = forms.ModelChoiceField(
        queryset=Account.objects.filter(students_Q).order_by("last_name"),
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )

    def __init__(self, *args, **kargs):
        """Filter accounts for students."""
        filters = kargs.pop("filters", tuple(tuple()))
        super(StudentSelectForm, self).__init__(*args, **kargs)
        for field, filt in filters:
            Qs = [Q(**{k: filt[k]}) for k in filt]
            if len(Qs) > 1:
                Qs_f = Qs[0]
                for Qs_i in Qs[1:]:
                    Qs_f = Qs_f | Qs_i
            else:
                Qs_f = Qs[0]
            self.fields[field].queryset = self.fields[field].queryset.filter(Qs_f)


class StaffSelectForm(forms.Form):
    """A Form to select staff with."""

    staff = forms.ModelChoiceField(
        queryset=Account.objects.filter(academic_Q).order_by("last_name"),
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )


class TutorSelectForm(forms.Form):
    """A form to setlect staff who have tutorial students with."""

    class Media:
        css = {"all": ["jquery-multiselect/jquery.multiselect.css"]}
        js = ["jquery-multiselect/jquery.multiselect.js", "jquery-multiselect/jquery.multiselect.init.js"]

    apt = forms.ModelMultipleChoiceField(
        queryset=Account.objects.filter(is_staff=True).order_by("last_name", "first_name"),
    )


class CohortSelectForm(forms.Form):
    cohort = forms.ModelChoiceField(
        required=False, queryset=Cohort.objects.all(), widget=Select(attrs={"onChange": "this.form.submit();"})
    )
