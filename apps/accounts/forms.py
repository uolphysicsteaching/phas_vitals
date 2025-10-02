# -*- coding: utf-8 -*-
# Django imports
from django import forms
from django.db.models import Count, Q
from django.forms.widgets import Select

# external imports
from dal import autocomplete
from minerva.models import Module

# app imports
from .models import Account, Cohort, academic_Q, students_Q


class StudentSelectForm(forms.Form):
    """A form to select students with."""

    user = forms.ModelChoiceField(
        queryset=Account.students.filter(students_Q).order_by("last_name"),
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


class AllStudentSelectForm(forms.Form):
    """A form to select students with."""

    user = forms.ModelChoiceField(
        queryset=Account.objects.filter(students_Q).order_by("last_name"),
        widget=autocomplete.ModelSelect2(url="accounts:Student_lookup", attrs={"onChange": "this.form.submit();"}),
    )

    def __init__(self, *args, **kargs):
        """Filter accounts for students."""
        filters = kargs.pop("filters", tuple(tuple()))
        super(AllStudentSelectForm, self).__init__(*args, **kargs)
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


class UserAdminForm(forms.ModelForm):
    """Tweaks to the User Admin account form."""

    class Meta:
        model = Account
        widgets = {
            "first_name": forms.TextInput(attrs={"size": 10}),
            "last_name": forms.TextInput(attrs={"size": 10}),
        }
        exclude = ()


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput())
    new_password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())


class ToggleActiveForm(forms.Form):
    """Tweaks to the User Admin account form."""

    number = forms.IntegerField(disabled=True, label="SID", required=False)
    display_name = forms.CharField(disabled=True, label="Student Name", required=False)
    username = forms.CharField(widget=forms.HiddenInput())
    is_active = forms.ChoiceField(choices=[(None, "-"), (False, "In-Active"), (True, "Active")])


class CohortFilterActivityScoresForm(forms.Form):
    """Form to filer accounts based on user activity score criteria."""

    module = forms.ModelChoiceField(
        queryset=Module.objects.annotate(tests_count=Count("tests")).filter(tests_count__gt=0)
    )

    what = forms.ChoiceField(
        choices=[
            ("activity_score", "Overall Activity"),
            ("Tutorial", "Tutorial Engagement"),
            ("VITALS", "VITALs passed %"),
            ("Lab Experiment", "Lab Sessions"),
            ("Code Tasks", "Code Assignments %"),
            ("Homework", "Homework Assignments %"),
        ],
        required=True,
        initial="activity",
    )
    how = forms.ChoiceField(
        choices=[("lte", "Less than or equal"), ("gt", "Greater than")],
        required=True,
        initial="lt",
    )
    value = forms.FloatField(required=True, initial=40.0)


class ToggleVITALForm(forms.Form):
    """Tweaks to the User Admin account form."""

    number = forms.IntegerField(disabled=True, label="SID", required=False)
    display_name = forms.CharField(disabled=True, label="Student Name", required=False)
    username = forms.CharField(widget=forms.HiddenInput())
    VITAL = forms.ModelChoiceField(
        queryset=Account.VITALS.field.model.objects.all(), widget=autocomplete.ModelSelect2(url="vitals:VITAL_lookup")
    )
    passed = forms.ChoiceField(choices=[(None, "-"), (False, "No Passed"), (True, "Passed")])
