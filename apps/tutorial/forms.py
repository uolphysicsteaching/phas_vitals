# -*- coding: utf-8 -*-
"""Forms for the tutorial app."""
# Python imports
from itertools import chain

# Django imports
import django.forms as forms
from django.core.exceptions import ValidationError
from django.db.models import F, Max, Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.forms.utils import flatatt
from django.forms.widgets import HiddenInput, Select
from django.utils.html import format_html

# external imports
from accounts.models import Account as Student
from ajax_select.fields import AutoCompleteSelectField
from util.forms import ObfuscatedCharField
from util.widgets import ObfuscatedTinyMCE

# app imports
from .models import (
    Answer,
    Attendance,
    Meeting,
    MeetingAttendance,
    MeetingQuestion,
    Question,
    TutorialAssignment,
)


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
                if isinstance(option_value.instance, Student):
                    display = option_value.instance.friendly_name
                else:
                    display = option_label
        output = format_html(
            '<h5 style="margin-top: 10px;">{display}</h5><input type="hidden" value="{value}"  {attrs}> ',
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
        """Form metadata for Attendance model."""

        model = Attendance
        exclude = ["type"]
        widgets = {"session": HiddenInput, "student": ReadOnlySelect}


class MeetingAttendanceForm(forms.ModelForm):
    """Edit the attendance outcome; ownership is assigned by the view."""

    class Meta:
        model = MeetingAttendance
        fields = ("status", "flag")


class MeetingForm(forms.ModelForm):
    """Create or edit a module-specific meeting template."""

    class Meta:
        model = Meeting
        fields = ("name", "module", "notes", "due_semester", "due_week")


class QuestionForm(forms.ModelForm):
    """Create or edit a reusable meeting question."""

    class Meta:
        model = Question
        fields = ("text", "type", "data")
        widgets = {"data": forms.Textarea(attrs={"rows": 3})}

    def clean_data(self):
        """Store an empty JSON list when optional choice metadata is omitted."""
        return self.cleaned_data.get("data") or []


class MeetingQuestionForm(forms.ModelForm):
    """Edit a linked Question's content from inside a Meeting formset."""

    text = ObfuscatedCharField(widget=ObfuscatedTinyMCE(attrs={"rows": 3}))
    type = forms.ChoiceField(choices=Question.Type.choices)
    data = forms.JSONField(
        required=False,
        initial=list,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=("For choice questions, enter JSON pairs such as " '[["yes", "Yes"], ["no", "No"]].'),
    )

    class Meta:
        model = MeetingQuestion
        fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["text"].initial = self.instance.question.text
            self.fields["type"].initial = self.instance.question.type
            self.fields["data"].initial = self.instance.question.data

    def clean(self):
        """Apply Question model validation to the inline fields."""
        cleaned_data = super().clean()
        if self.cleaned_data.get("DELETE"):
            return cleaned_data
        if not all(name in cleaned_data for name in ("text", "type", "data")):
            return cleaned_data
        question = self.instance.question if self.instance.pk else Question()
        question.text = cleaned_data["text"]
        question.type = cleaned_data["type"]
        question.data = cleaned_data.get("data") or []
        try:
            question.full_clean()
        except ValidationError as error:
            for field, messages in error.message_dict.items():
                for message in messages:
                    self.add_error(field if field in self.fields else None, message)
        return cleaned_data

    def save_question(self):
        """Persist the Question represented by this inline form."""
        question = self.instance.question if self.instance.pk else Question()
        question.text = self.cleaned_data["text"]
        question.type = self.cleaned_data["type"]
        question.data = self.cleaned_data.get("data") or []
        question.full_clean()
        question.save()
        return question


class BaseMeetingQuestionFormSet(BaseInlineFormSet):
    """Save linked questions in the order selected in the frontend."""

    ordering_widget = forms.HiddenInput

    def save(self, commit=True):
        if not commit:
            raise ValueError("Meeting question formsets must be saved atomically.")

        links = MeetingQuestion.objects.filter(meeting=self.instance)
        maximum = links.aggregate(value=Max("position"))["value"] or 0
        links.update(position=F("position") + maximum + len(self.forms) + 1)

        for form in self.deleted_forms:
            if form.instance.pk:
                form.instance.delete()

        saved = []
        for position, form in enumerate(self.ordered_forms, start=1):
            question = form.save_question()
            link = form.instance
            link.meeting = self.instance
            link.question = question
            link.position = position
            link.save()
            saved.append(link)
        return saved


MeetingQuestionFormSet = inlineformset_factory(
    Meeting,
    MeetingQuestion,
    form=MeetingQuestionForm,
    formset=BaseMeetingQuestionFormSet,
    fields=(),
    extra=0,
    can_delete=True,
    can_order=True,
)


class MeetingAnswersForm(forms.Form):
    """Build typed answer fields from a meeting's ordered question template."""

    field_prefix = "question_"

    def __init__(self, *args, meeting, attendance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.meeting = meeting
        self.attendance = attendance
        existing = {}
        if attendance and attendance.pk:
            existing = {answer.question_id: answer for answer in attendance.answers.all()}
        self.questions = list(meeting.ordered_questions)
        for question in self.questions:
            name = self.field_name(question)
            initial = None
            if question.pk in existing:
                initial = existing[question.pk].data.get(question.type)
                if question.type == Question.Type.YES_NO:
                    initial = "true" if initial else "false"
            self.fields[name] = self.make_field(question, initial)

    @classmethod
    def field_name(cls, question):
        """Return the stable form-field name for a question."""
        return f"{cls.field_prefix}{question.pk}"

    @staticmethod
    def make_field(question, initial):
        """Map a question type to the corresponding Django form field."""
        common = {"label": question, "required": False, "initial": initial}
        if question.type == Question.Type.YES_NO:
            return forms.TypedChoiceField(
                choices=(("", "---------"), ("true", "Yes"), ("false", "No")),
                coerce=lambda value: value == "true",
                empty_value=None,
                **common,
            )
        if question.type == Question.Type.TEXT:
            return forms.CharField(widget=forms.Textarea, **common)
        if question.type == Question.Type.NUMBER:
            return forms.FloatField(**common)
        if question.type == Question.Type.SELECT:
            return forms.ChoiceField(choices=question.choices, **common)
        if question.type == Question.Type.MULTI_SELECT:
            return forms.MultipleChoiceField(choices=question.choices, **common)
        raise ValueError(f"Unsupported question type: {question.type}")

    def save(self, attendance):
        """Create, update, or remove answers using stable question identifiers."""
        for question in self.questions:
            value = self.cleaned_data[self.field_name(question)]
            if value in (None, "", []):
                Answer.objects.filter(attendance=attendance, question=question).delete()
                continue
            answer = Answer.objects.filter(attendance=attendance, question=question).first() or Answer(
                attendance=attendance,
                question=question,
            )
            answer.data = {question.type: value}
            answer.full_clean()
            answer.save()


class TutorialAssignmentForm(forms.ModelForm):
    """Form for managing tutorial assignment."""

    class Meta:
        """Form metadata for TutorialAssignment model."""

        model = TutorialAssignment
        exclude = []

    class Media:
        """Media definitions for the form."""

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
