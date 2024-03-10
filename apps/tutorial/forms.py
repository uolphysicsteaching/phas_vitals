# -*- coding: utf-8 -*-
"""Forms for the tutorial app."""
# Python imports
from itertools import chain

# Django imports
import django.forms as forms
from django.db.models import Q
from django.forms.utils import flatatt
from django.forms.widgets import HiddenInput, Select
from django.utils.html import format_html

# external imports
from accounts.models import Account as Student
from ajax_select.fields import AutoCompleteSelectField

# app imports
from .models import Attendance, TutorialAssignment


class ReadOnlySelect(Select):
    """A select widget that is read-only.

    This should replace the Select widget with a disabled text widget displaying the value,
    and hidden field with the actual id.
    """

    def render(self, name, value, attrs=None, choices=(), renderer=None):
        """Render the widget."""
        final_attrs = self.build_attrs(attrs, {"name": name})
        display = "None"
        for option_value, option_label in chain(self.choices, choices):
            if str(option_value) == str(value):
                display = option_label
        output = format_html(
            '<h3 style="margin-top: 10px;">{display}</h3><input type="hidden" value="{value}"  {attrs}> ',
            display=display,
            value=value,
            attrs=flatatt(final_attrs),
        )

        return output


class AttendanceFormSet(forms.models.BaseModelFormSet):
    """Make a formset for recording attendance."""

    @property
    def sorted_forms(self):
        """Sort the forms by student name."""
        if len(getattr(self.forms[0], "initial", {})) == 0:
            return self.forms
        forms = {}
        for form in self.forms:
            data = form.initial
            student = data["student"]
            if isinstance(student, int):
                student = Student.objects.get(id=form.initial["student"])
            forms[(student.last_name, student.first_name)] = form

        forms.pop(None, None)

        return [forms[form] for form in sorted(forms)]

    def __iter__(self):
        """Iterate over the formset."""
        return iter(self.sorted_forms)

    def __getitem__(self, index):
        """Implement indexing of the formset."""
        return self.sorted_forms[index]


class EngagementEntryForm(forms.ModelForm):
    """Form class for recording engagement with the tutorial."""

    class Meta:
        model = Attendance
        exclude = ["type"]
        widgets = {"session": HiddenInput, "student": ReadOnlySelect}


class TutorialAssignmentForm(forms.ModelForm):
    """Form for managing tutorial assignment."""

    class Meta:
        model = TutorialAssignment
        exclude = []

    class Media:
        js = ("js/django-formset.js",)

    student = AutoCompleteSelectField(
        "user",
        required=True,
        help_text="Start typing a student's name or email.",
    )

    def __init__(self, *args, **kargs):
        """Construct form with additional filter."""
        filters = kargs.pop("filters", tuple(tuple()))
        super(TutorialAssignmentForm, self).__init__(*args, **kargs)
        self.apply_filter(filters)

    def apply_filter(self, filters):
        """Apply filters to a query set for a field."""
        field = None
        for field, filt in filters:
            if not isinstance(filt, list):
                filt = [filt]
            for i, f in enumerate(filt):
                if i == 0:
                    QS = Q(**f)
                else:
                    QS = QS | Q(**f)
            if field is not None:
                self.fields[field].queryset = self.fields[field].queryset.filter(QS).distinct()
