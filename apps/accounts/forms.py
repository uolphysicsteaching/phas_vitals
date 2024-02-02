# -*- coding: utf-8 -*-
# Django imports
import django.utils.timezone as tz
from django.db.models import Count, Q
from django.forms.widgets import Select

# external imports
import floppyforms as forms

# app imports
from .models import Account, Cohort, academic_Q, students_Q


class StudentSelectForm(forms.Form):
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
    staff = forms.ModelChoiceField(
        queryset=Account.objects.filter(academic_Q).order_by("last_name"),
        widget=Select(attrs={"onChange": "this.form.submit();"}),
    )


class CohortSelectForm(forms.Form):
    cohort = forms.ModelChoiceField(
        required=False, queryset=Cohort.objects.all(), widget=Select(attrs={"onChange": "this.form.submit();"})
    )
