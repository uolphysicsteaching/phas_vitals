# -*- coding: utf-8 -*-
"""Views to do with managing Student engagement with the tutorials."""
# Django imports
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone as tz
from django.views.generic import DetailView, FormView, ListView, UpdateView
from django.views.generic.edit import FormMixin

# external imports
import numpy as np
import pandas as pd
from accounts.forms import CohortSelectForm
from accounts.models import Account, Cohort
from extra_views import ModelFormSetView
from util.forms import FileSelectForm
from util.views import (
    IsStaffViewMixin,
    IsStudentViewixin,
    IsSuperuserViewMixin,
)

# app imports
from ..forms import EngagementEntryForm
from ..models import Attendance, Session, SessionType, Tutorial


class StudentEngagementSummary(IsStaffViewMixin, FormMixin, ListView):
    """Produce a table of students in tutorial groups with attendance data."""

    context_object_name = "groups"
    model = Tutorial
    template_name = "tutorial/engagement_summary.html"
    form_class = CohortSelectForm

    def get_initial(self):
        if isinstance(self.kwargs.get("cohort", None), str):
            try:
                self.kwargs["cohort"] = Cohort.objects.get(name=self.kwargs["cohort"])
            except ObjectDoesNotExist:
                del self.kwargs["cohort"]
        return {"cohort": self.kwargs.setdefault("cohort", Cohort.current)}

    def get_queryset(self):
        cohort = self.get_initial()["cohort"]
        ret = Tutorial.objects.filter(cohort=cohort).order_by("tutor__last_name")
        if self.kwargs.get("code", "") != "":
            ret = ret.filter(code__iexact=self.kwargs["code"])
        else:
            ret = ret.filter(tutor=self.request.user)
        return ret

    def get_context_data(self, **kwargs):
        """The context data here needs to include a list of marktypes and also the current cohort."""
        context = super().get_context_data(**kwargs)
        cohort = self.kwargs["cohort"]
        semester = int(self.kwargs.get("semester", 1 if tz.now().month >= 8 else 2))
        context["cohorts"] = Cohort.objects.all()
        context["semester"] = semester
        context["cohort"] = cohort
        context["sessions"] = Session.objects.filter(cohort=cohort, semester=semester)
        return context

    def post(self, request, *args, **kargs):
        """Handle the user changing Cohort."""
        form = self.form_class(self.request.POST)
        if form.is_valid():
            self.kwargs["cohort"] = form.cleaned_data["cohort"].name
        return self.get(request, *args, **kargs)


class SubmitStudentEngagementView(IsStaffViewMixin, ModelFormSetView):
    """Handles the generation and handling of the tutorial attendance dialog form."""

    template_name = "tutorial/forms/engagement_submission.html"
    form_class = EngagementEntryForm
    model = Attendance

    def get_initial(self):
        return {"cohort": self.kwargs.setdefault("cohort", Cohort.current)}

    def get_context_data(self, **kwargs):
        """The context data here needs to include a list of marktypes and also the current cohort."""
        context = super().get_context_data(**kwargs)
        context["url"] = "/tutorial/engagement/submit/" + self.kwargs["session"]
        return context

    def get_success_url(self):
        group, session = self.kwargs["session"].split(":")
        session = Session.objects.get(pk=int(session))
        return f"/tutorial/engagement_view/{session.semester}/{session.cohort.name}"

    def get_queryset(self):
        group, session = self.kwargs["session"].split(":")
        session = Session.objects.get(pk=int(session))
        group = Tutorial.objects.get(pk=int(group))
        for student in group.students.all().distinct():
            inst, _ = Attendance.objects.get_or_create(student=student, session=session, type=SessionType.TUTORIAL)

        ret = Attendance.objects.filter(session=session, student__tutorial_group=group, type=SessionType.TUTORIAL)
        return ret

    def get_factory_kwargs(self):
        ret = {
            "extra": 0,
            "max_num": None,
            "can_order": False,
            "can_delete": False,
            "form": self.form_class,
        }
        group, session = self.kwargs["session"].split(":")
        session = Session.objects.get(pk=int(session))
        group = Tutorial.objects.get(pk=int(group))
        qs = Attendance.objects.filter(session=session, student__tutorial_group=group, type=SessionType.TUTORIAL)
        ret["extra"] = max(0, len(group.students.all()) - len(qs.all()))
        return ret


class AdminEngagementSummaryView(StudentEngagementSummary):
    """Produce a view of a cohort of student engagement."""

    template_name = "tutorial/admin/engagement_summary.html"

    def get_queryset(self):
        cohort = self.get_initial()["cohort"]  # force sorting out our cohort
        ret = (
            Tutorial.objects.filter(cohort=cohort)
            .prefetch_related("students", "tutor", "cohort", "cohort__sessions", "students__attendance")
            .order_by("tutor__last_name")
        )
        return ret


class AdminSubmitStudentEngagementView(IsSuperuserViewMixin, UpdateView):
    """Handles the generation and handling of the tutorial attendance dialog form."""

    template_name = "tutorial/forms/admin_engagement_submission.html"
    form_class = EngagementEntryForm
    model = Attendance
    success_url = "/"

    def get_context_data(self, **kwargs):
        """The context data here needs to include a list of marktypes and also the current cohort."""
        context = super().get_context_data(**kwargs)
        context["url"] = (
            f"/tutorial/engagement/admin_submit/session_{self.kwargs.get('student')}_{self.kwargs.get('session')}"
        )
        return context

    def form_valid(self, form):
        super().form_valid(form)
        return JsonResponse({"status": True, "data": self.object.score})

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        obj = queryset.filter(
            student__pk=self.kwargs.get("student"), session__pk=self.kwargs.get("session"), type=SessionType.TUTORIAL
        ).first()
        return obj


class AdminResultStudentEngagementView(IsSuperuserViewMixin, DetailView):
    """Handles the generation and handling of the tutorial attendance dialog form."""

    template_name = "tutorial/forms/admin_engagement_result.html"
    model = Attendance
    context_object_name = "result"

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        obj = queryset.filter(
            student__pk=self.kwargs.get("student"), session__pk=self.kwargs.get("session"), type=SessionType.TUTORIAL
        ).first()
        return obj


class LabAttendanceUpload(IsSuperuserViewMixin, FormView):
    """Load a spreadsheet with a Student ID and Tutor ID columns."""

    form_class = FileSelectForm
    template_name = "tutorial/admin/lab_attendance.html"  # Replace with your template.
    success_url = "/tutorial/admin/lab_attendance/"  # Replace with your URL or reverse().
    report = None
    failed = []

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist("spreadsheet")
        if form.is_valid():
            if len(files) != 1:
                raise ValidationError("Execting a single xlsx file.")
            for f in files:
                f = f.file.name
                try:
                    self.report = pd.read_excel(f, header=None)
                    row, col = np.where(self.report.values == "Student ID")
                    if len(row) != 1:
                        raise ValueError("expected one and onely one cell labelled Student ID")
                    self.report = pd.read_excel(f, header=row[0])
                except Exception as e:
                    raise ValidationError(f"Error reading excel file {e}") from e
            if self.report is None:
                raise ValidationError("Execting a single xlsx file.")
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Do the actual processing of the uplloaded files."""
        self.failed = []
        cohort = Cohort.current
        sessions = Session.past(cohort=cohort)
        headers = {f"S{session.semester} Wk{session.week}": session for session in sessions}
        sids = {x.number: x for x in Account.objects.filter(cohort=cohort)}
        compact = []
        self.report.rename(
            columns={x: x.strip().title() for x in self.report.columns if x.strip() != "Student ID"}, inplace=True
        )
        for ix, row in self.report.iterrows():
            try:
                sid = int(np.round(row["Student ID"]))
            except ValueError:
                continue  # Can't get a SID
            if sid not in sids:
                self.failed.append(
                    {"Student": sid, "reason": f"Unable to locate student with ID {sid} - not enrolled in PHYS1000?"}
                )
                continue
            out = {"Student ID": sid}
            for session in headers:
                if session not in row or not isinstance(row[session], (int, float)) or np.isnan(row[session]):
                    if session not in row:
                        self.failed.append({"Student": "All", "reason": f"Could not match session {session} to data"})
                    out[session] = np.NaN
                else:
                    out[session] = float(row[session])
            compact.append(out)
        compact = pd.DataFrame(compact)
        with transaction.atomic():
            for ix, row in compact.iterrows():
                for header, session in headers.items():
                    if not np.isnan(row[header]):
                        new, _ = Attendance.objects.get_or_create(
                            student=sids[int(row["Student ID"])], session=session, type=SessionType.LAB
                        )
                        score = int(row[header])
                        score = [0, 1, 3, 2, 4][score]  # Remap scores 2 and 3 to give more credit for handing work in
                        new.score = score
                        new.save()
                    else:
                        Attendance.objects.filter(
                            student=sids[int(row["Student ID"])], session=session, type=SessionType.LAB
                        ).delete()
        context = self.get_context_data(form=form)
        context["success"] = True
        context["errors"] = self.failed
        return self.render_to_response(context=context)
