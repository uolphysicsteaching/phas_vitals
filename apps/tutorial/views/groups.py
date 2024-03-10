# -*- coding: utf-8 -*-
"""Views to support tutorial group admin."""

# Django imports
from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    ValidationError,
)
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.views.generic import DetailView, FormView

# external imports
import pandas as pd
from accounts.models import Account, Cohort
from util.forms import FileSelectForm
from util.views import IsStaffViewMixin, IsSuperuserViewMixin

# app imports
from ..models import Meeting, MeetingAttendance, Tutorial, TutorialAssignment


class AssignTutorGroupsView(IsSuperuserViewMixin, FormView):
    """Load a spreadsheet with a Student ID and Tutor ID columns."""

    form_class = FileSelectForm
    template_name = "tutorial/admin/assign.html"  # Replace with your template.
    success_url = "/tutorial/admin/assign/"  # Replace with your URL or reverse().
    report = None
    failed = []

    def get_context_data(self, **kwargs):
        """The context data here needs to include a list of marktypes and also the current cohort."""
        context = super(AssignTutorGroupsView, self).get_context_data(**kwargs)
        context["failed"] = self.failed
        return context

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
                    self.report = pd.read_excel(f)
                except Exception as e:
                    raise ValidationError("Execting a single xlsx file.") from e
            if self.report is None:
                report = self.report
                archive = self.archive
                raise ValidationError("Execting a single xlsx file.")
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """Do the actual processing of the uplloaded files."""
        self.failed = []
        cohort = Cohort.current
        for row in self.report.T.to_dict().values():
            try:
                if isinstance(row["Student ID"], str):
                    student = Account.objects.get(username=row["Student ID"].split("@")[0].strip())
                else:
                    student = Account.objects.get(number=row["Student ID"])
            except ObjectDoesNotExist:
                if not isinstance(row.get("Tutor ID", None), str) or row.get("Tutor ID", None).strip() == "":
                    continue
                self.failed.append({"Student": row["Student ID"], "reason": "Student not found!"})
                continue

            try:
                if not isinstance(row.get("Tutor ID", None), str):
                    continue  # No tutor set in spreadsheet so ignore
                tutor = Account.objects.get(
                    Q(last_name__iexact=row["Tutor ID"].strip()) | Q(username=row["Tutor ID"].strip()), is_staff=True
                )
            except ObjectDoesNotExist:
                self.failed.append(
                    {"Student": row["Student ID"], "reason": "Tutor {Tutor ID} not found!".format(**row)}
                )
                continue
            except MultipleObjectsReturned:
                self.failed.append(
                    {"Student": row["Student ID"], "reason": "Tutor {Tutor ID} ambiguous!".format(**row)}
                )
                continue
            if row.get("Group ID", None) in [None, ""]:
                row["Group ID"] = f"{tutor.initials}_{cohort.name}"
            elif isinstance(row["Group ID"], int):
                row["Group ID"] = f"{tutor.initials}_{cohort}/{row['Group ID']}"
            else:
                row["Group ID"] = str(row["Group ID"])

            tutorial, new = Tutorial.objects.get_or_create(
                tutor=tutor,
                cohort=cohort,
                code=row["Group ID"],
            )
            if new:
                tutorial.save()
            try:
                assignment, new = TutorialAssignment.objects.get_or_create(student=student, tutorial=tutorial)
            except IntegrityError:
                student.cohort = tutorial.cohort
                student.save()
                old_assign = TutorialAssignment.objects.filter(student=student)
                old_assign.delete()
                assignment, new = TutorialAssignment.objects.get_or_create(student=student, tutorial=tutorial)
                self.failed.append(
                    {
                        "Student": row["Student ID"],
                        "reason": f"Moved from {old_assign.first().tutorial.code} to {tutorial.code}",
                    }
                )
            assignment.save()
        context = self.get_context_data(form=form)
        context["success"] = True
        context["errors"] = self.failed
        return self.render_to_response(context=context)


class ToggleTutorialAssignmentField(IsStaffViewMixin, DetailView):
    """Toggle the Academic Integrity Test or PebblePadForm fields."""

    model = TutorialAssignment
    context_object_name = "assignment"

    def get_object(self, queryset=None):
        """Get the assignment from the username in the url."""
        acc = Account.objects.get(username=self.kwargs.get("user", ""))
        return acc.tutorial_group_assignment

    def render_to_response(self, context, **response_kwargs):
        """Redirect back to the staff-student summary page after toggling the filed."""
        obj = context["assignment"]
        component = self.kwargs.get("component", "")
        mapping = {"AIT": "integrity_test", "PF": "pebblepad_form"}
        if component not in mapping:
            return HttpResponseNotFound()
        val = not getattr(obj, mapping[component], False)
        setattr(obj, mapping[component], val)
        obj.save()
        student = obj.student
        # mtype = MarkType.objects.get(code=component)
        # score = getattr(student, f"{component}_mark")
        # tutorial = student.tutorial_group_assignment.tutorial
        # msheet, new = Marksheet.objects.get_or_create(student=student, tutorial=tutorial, type=mtype)
        # msheet.score = score
        # msheet.submitter = self.request.user
        # msheet.save()
        return HttpResponseRedirect(f"/accounts/staff_view/{obj.student.username}")


class ToggleMeeting(IsStaffViewMixin, DetailView):
    """Toggle the Academic Integrity Test or PebblePadForm fields."""

    model = Meeting
    context_object_name = "meeting"
    slug_field = "pk"

    def render_to_response(self, context, **response_kwargs):
        """Redirect back to the staff-student summary page after toggling the filed."""
        meeting = context["meeting"]
        try:
            student = Account.objects.get(username=self.kwargs.get("username", None))
        except ObjectDoesNotExist:
            return HttpResponseNotFound()
        if student.cohort != meeting.cohort:
            return HttpResponseNotFound()
        if meeting.students.filter(username=student.username).count() == 1:
            meeting.students.remove(meeting.students.get(username=student.username))
        else:
            new = MeetingAttendance(student=student, tutor=self.request.user, meeting=meeting)
            new.save()
            x = new.pk
        meeting.save()
        return HttpResponseRedirect(f"/accounts/staff_view/{student.username}")
