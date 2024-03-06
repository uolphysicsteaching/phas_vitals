# -*- coding: utf-8 -*-
"""Views to support tutorial administration"""

# Python imports
from collections import OrderedDict

# Django imports
from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    ValidationError,
)
from django.db import transaction
from django.utils import timezone as tz
from django.utils.safestring import mark_safe
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import FormMixin, FormView

# external imports
import pandas as pd
from accounts.forms import CohortSelectForm
from accounts.models import Account, Cohort
from django_tables2.views import SingleTableView
from util.forms import FileSelectForm
from util.views import IsStaffViewMixin, IsSuperuserViewMixin

# app imports
from ..models import Meeting, Tutorial, TutorialAssignment, students_Q
from ..tables import BaseMarkTable, BaseTable, MarkColumn


class AdminDashboardView(IsSuperuserViewMixin, FormMixin, TemplateView):
    """Collect various admin tools in one place."""

    template_name = "tutorial/admin/dashboard.html"
    form_class = CohortSelectForm

    def get_initial(self) -> dict:
        return {"cohort": self.kwargs.setdefault("cohort", Cohort.current)}

    def get_context_data(self, **kwargs):
        """The context data here needs to include a list of marktypes and also the current cohort."""
        context = super(AdminDashboardView, self).get_context_data(**kwargs)
        context["semester"] = int(self.kwargs.get("semester", 1 if tz.now().month >= 8 else 2))
        try:
            context["cohort"] = Cohort.objects.get(name=self.kwargs.get("cohort", ""))
        except (ObjectDoesNotExist, MultipleObjectsReturned):
            context["cohort"] = ""
        return context

    def post(self, request, *args, **kargs):
        """Handle the user changing Cohort."""
        form = self.form_class(self.request.POST)
        if form.is_valid():
            self.kwargs["cohort"] = form.cleaned_data["cohort"].name
        return self.get(request, *args, **kargs)


class MeetingsSummary(IsSuperuserViewMixin, FormMixin, SingleTableView):
    """Provides the Module leaders overview of which students have been recorded as attending meetings."""

    template_name = "tutorial/admin/meetings_summary.html"
    context_table_name = "students"
    table_pagination = False
    form_class = CohortSelectForm

    def get_table_class(self):
        """Construct the django-tables2 table class for this view."""
        meetings = Meeting.objects.all()
        cohort = self.kwargs.get("cohort", "")
        try:
            meetings = meetings.filter(cohort=Cohort.objects.get(name=cohort))
        except ObjectDoesNotExist:
            pass
        attrs = OrderedDict()
        for x in meetings:
            attrs[x.slug] = MarkColumn(verbose_name=x.name)
        try:
            meta = getattr(BaseTable, "Meta")
            attrs["Meta"] = meta
        except AttributeError:
            pass
        klass = type("DynamicTable", (BaseTable,), attrs)
        return klass

    def get_context_data(self, **kwargs):
        """Get the cohort into context from the slug."""
        cohort = self.kwargs.get("cohort", "")
        context = super().get_context_data(**kwargs)
        try:
            context["cohort"] = Cohort.objects.get(name=cohort)
        except (ObjectDoesNotExist, MultipleObjectsReturned):
            context["cohort"] = ""
        return context

    def get_table_data(self):
        """Fill out the table with data, creating the entries for the MarkType columns to interpret."""
        cohort = self.kwargs.get("cohort", self.get_initial().get("cohort", Cohort.current.name))
        try:
            cohort = Cohort.objects.get(name=cohort)
        except (ObjectDoesNotExist, MultipleObjectsReturned):
            cohort = None
        students = Account.objects.filter(students_Q).prefetch_related(
            "tutorial_group_assignment__tutorial", "tutorial_group_assignment__tutorial__tutor"
        )
        meetings = Meeting.objects.all()
        if cohort:
            meetings = meetings.filter(cohort=cohort)
            students = students.filter(cohort=cohort).prefetch_related("marksheets")
        table = []
        for student in students:
            record = dict(
                [
                    ("student", "Unknown"),
                    ("tutor", "No Tutor!"),
                ]
            )
            for meeting in meetings:
                record[meeting.slug] = None if meeting.due_date > tz.now().date() else False
            record["student"] = mark_safe('<a href="/accounts/staff_view/{}">{}</a>'.format(student.username, student))
            if hasattr(student, "tutorial_group") and student.tutorial_group.first():
                record["tutor"] = student.tutorial_group.first().tutor.initials
            for meeting in meetings:
                if meeting in student.meetings.all():
                    record[meeting.slug] = "<img src='/static/admin/img/icon-yes.svg' alt='Yes'/>"
            table.append(record)
        return table

    def get_queryset(self):
        """Use get_table_data instead of a queryset."""
        return self.get_table_data()


class StudentMarkingSummary(IsStaffViewMixin, FormMixin, ListView):
    context_object_name = "groups"
    model = Tutorial
    template_name = "tutorial/marking_summary.html"
    form_class = CohortSelectForm

    def get_queryset(self):
        return Tutorial.objects.filter(tutor=self.request.user)

    def get_context_data(self, **kwargs):
        """The context data here needs to include a list of marktypes and also the current cohort."""
        context = super(StudentMarkingSummary, self).get_context_data(**kwargs)
        return context


class AcademicIntegrityUpload(IsSuperuserViewMixin, FormView):
    """Handle Uploading Academic Integrity Test Spreadsheet from Minerva."""

    form_class = FileSelectForm
    template_name = "tutorial/admin/ai_upload.html"  # Replace with your template.
    success_url = "/tutorial/admin/ai_upload/"  # Replace with your URL or reverse().
    report = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["failed"] = getattr(self, "failed", [])
        return context

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist("spreadsheet")
        if form.is_valid():
            if len(files) != 1:
                raise ValidationError("Execting a single csv file.")
            for f in files:
                f = f.file.name
                try:
                    self.report = pd.read_csv(f)
                except Exception as e:
                    raise ValidationError("Execting a single csv file.") from e
            if self.report is None:
                raise ValidationError("Execting a single csv file.")
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Do the actual processing of the uplloaded files."""
        self.report = self.report[
            self.report["Pass Date"].notna()
        ]  # Keep only those records where the student has passed
        with transaction.atomic():
            for student in TutorialAssignment.objects.filter(student__number__in=self.report["Student ID"]):
                student.integrity_test = True
                student.save()
                # mtype = MarkType.objects.get(code="AIT")
                score = getattr(student.student, "AIT_mark")
                tutorial = student.tutorial
                # msheet, new = Marksheet.objects.get_or_create(student=student.student, tutorial=tutorial, type=mtype)
                # msheet.score = score
                # msheet.submitter = self.request.user
                # msheet.save()

        return super().form_valid(form)
