# -*- coding: utf-8 -*-
# Django imports
from django.db.models import Q, Count
from django.forms.widgets import Select
from django import forms

# app imports
from .models import Account, Cohort, academic_Q, students_Q


class StudentSelectForm(forms.Form):
    
    """A form to select students with."""
    
    user = forms.ModelChoiceField(
        queryset=Account.objects.filter(students_Q).order_by("last_name"),
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )

    def __init__(self, *args, **kargs):
        filters = kargs.pop("filters", tuple(tuple()))
        super(StudentSelectForm, self).__init__(*args, **kargs)
        for field, filter in filters:
            Qs = [Q(**{k: filter[k]}) for k in filter]
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
        js = ["jquery-multiselect/jquery.multiselect.js","jquery-multiselect/jquery.multiselect.init.js"]

    apt = forms.ModelMultipleChoiceField(
        queryset=Account.objects.annotate(tutee_count=Count("tutees"))
        .filter(tutee_count__gt=0)
        .order_by("last_name", "first_name"),
        )

class CohortSelectForm(forms.Form):
    cohort = forms.ModelChoiceField(
        required=False, queryset=Cohort.objects.all(), widget=Select(attrs={"onChange": "this.form.submit();"})
    )
