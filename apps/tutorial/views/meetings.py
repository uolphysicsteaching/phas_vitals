"""CRUD views for student meeting records."""

# Django imports
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

# external imports
from accounts.models import Account
from util.views import (
    IsStaffViewMixin,
    IsStudentViewixin,
    IsSuperuserViewMixin,
    RedirectView,
)

# app imports
from ..forms import (
    MeetingAnswersForm,
    MeetingAttendanceForm,
    MeetingForm,
    MeetingQuestionFormSet,
    QuestionForm,
)
from ..models import Meeting, MeetingAttendance, Question


def tutor_for(student):
    """Return the tutor currently assigned to a student, if one exists."""
    try:
        return student.tutorial_group_assignment.tutorial.tutor
    except ObjectDoesNotExist:
        return None


class MeetingDetailView(IsStudentViewixin, DetailView):
    """Display a meeting template's notes and ordered questions."""

    model = Meeting
    context_object_name = "meeting"
    template_name = "tutorial/meeting_detail.html"
    queryset = Meeting.objects.select_related("module")

    def test_func(self):
        """Allow staff, or a student enrolled on the meeting's module, to view it."""
        if not super().test_func():
            return False
        return self.request.user.is_staff or self.get_object().is_for(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["questions"] = self.object.ordered_questions
        return context


class MeetingManageListView(IsSuperuserViewMixin, ListView):
    """List meeting templates for superuser maintenance."""

    model = Meeting
    context_object_name = "meetings"
    template_name = "tutorial/meeting_manage_list.html"
    queryset = Meeting.objects.select_related("module").all()


class MeetingFormSetMixin:
    """Save a meeting and its editable, ordered question formset together."""

    form_class = MeetingForm
    model = Meeting
    template_name = "tutorial/meeting_manage_form.html"

    def get_question_formset(self):
        kwargs = {"instance": self.object, "prefix": "questions"}
        if self.request.method in ("POST", "PUT"):
            kwargs |= {"data": self.request.POST, "files": self.request.FILES}
        return MeetingQuestionFormSet(**kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("question_formset", self.get_question_formset())
        return context

    def form_valid(self, form):
        question_formset = self.get_question_formset()
        if not question_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, question_formset=question_formset))
        with transaction.atomic():
            self.object = form.save()
            question_formset.instance = self.object
            question_formset.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("tutorial:meeting-manage-update", kwargs={"pk": self.object.pk})


class MeetingManageCreateView(IsSuperuserViewMixin, MeetingFormSetMixin, CreateView):
    """Create a meeting template and its ordered questions."""


class MeetingManageUpdateView(IsSuperuserViewMixin, MeetingFormSetMixin, UpdateView):
    """Edit a meeting template and its ordered questions."""

    def get_success_url(self):
        """Return to the meeting list after a successful update."""
        return reverse("tutorial:meeting-manage-list")


class MeetingManageDeleteView(IsSuperuserViewMixin, DeleteView):
    """Delete a meeting template and its associated records."""

    model = Meeting
    context_object_name = "meeting"
    template_name = "tutorial/meeting_manage_confirm_delete.html"
    success_url = reverse_lazy("tutorial:meeting-manage-list")


class QuestionManageListView(IsSuperuserViewMixin, ListView):
    """List reusable questions for superuser maintenance."""

    model = Question
    context_object_name = "questions"
    template_name = "tutorial/question_manage_list.html"


class QuestionManageCreateView(IsSuperuserViewMixin, CreateView):
    """Create a reusable meeting question."""

    model = Question
    form_class = QuestionForm
    template_name = "tutorial/question_manage_form.html"
    success_url = reverse_lazy("tutorial:question-manage-list")


class QuestionManageUpdateView(IsSuperuserViewMixin, UpdateView):
    """Edit a reusable meeting question."""

    model = Question
    form_class = QuestionForm
    template_name = "tutorial/question_manage_form.html"
    success_url = reverse_lazy("tutorial:question-manage-list")


class QuestionManageDeleteView(IsSuperuserViewMixin, DeleteView):
    """Delete an unused meeting question."""

    model = Question
    context_object_name = "question"
    template_name = "tutorial/question_manage_confirm_delete.html"
    success_url = reverse_lazy("tutorial:question-manage-list")

    def form_valid(self, form):
        """Explain why a referenced question cannot be deleted."""
        try:
            return super().form_valid(form)
        except ProtectedError:
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    protected_error=(
                        "This question is still used by a meeting or attendance record. "
                        "Remove those references before deleting it."
                    ),
                ),
                status=409,
            )


class MeetingAttendanceActionView(RedirectView):
    """Send each permitted role to the appropriate action for a meeting."""

    def dispatch(self, request, *args, **kwargs):
        self.meeting = get_object_or_404(Meeting, pk=kwargs["meeting_pk"])
        self.student = get_object_or_404(Account, pk=kwargs["student_pk"])
        self.attendance = MeetingAttendance.objects.filter(meeting=self.meeting, student=self.student).first()
        return super().dispatch(request, *args, **kwargs)

    def detail_view(self):
        """Prepare the record primary key for the detail/update views."""
        if self.attendance is None:
            return None
        self.kwargs["pk"] = self.attendance.pk
        return MeetingAttendanceDetailView

    def get_superuser_view(self, request):
        """Allow superusers to create a missing record or read an existing one."""
        if request.user.is_authenticated and request.user.is_superuser:
            view = self.detail_view()
            if view is None:
                return MeetingAttendanceCreateView
            return view
        return None

    def get_staff_view(self, request):
        """The assigned tutor creates a missing record or updates an existing one."""
        if not request.user.is_authenticated or not request.user.is_staff:
            return None
        if tutor_for(self.student) != request.user:
            raise PermissionDenied
        if self.attendance is None:
            return MeetingAttendanceCreateView
        self.kwargs["pk"] = self.attendance.pk
        return MeetingAttendanceUpdateView

    def get_logged_in_view(self, request):
        """A student may read their own existing record."""
        if not request.user.is_authenticated or request.user.pk != self.student.pk:
            raise PermissionDenied
        view = self.detail_view()
        if view is None:
            raise Http404("No attendance record exists for this meeting.")
        return view


class TutorMeetingAccessMixin(IsStaffViewMixin):
    """Allow a superuser or the tutor currently assigned to the student."""

    def get_access_student(self):
        """Return the student whose tutor controls this request."""
        raise NotImplementedError

    def test_func(self):
        """Require an authorised staff user and an available, applicable meeting."""
        student = self.get_access_student()
        return (
            super().test_func()
            and (self.request.user.is_superuser or tutor_for(student) == self.request.user)
            and self.get_meeting().is_available_for(student)
            and self.get_meeting().is_for(student)
        )


class MeetingRecordFormMixin:
    """Share template-answer handling between create and update views."""

    form_class = MeetingAttendanceForm
    model = MeetingAttendance
    template_name = "tutorial/meetingattendance_form.html"

    def get_answers_form(self):
        """Construct the dynamic answers form for this meeting record."""
        kwargs = {
            "meeting": self.get_meeting(),
            "attendance": (self.object if getattr(self, "object", None) and self.object.pk else None),
        }
        if self.request.method in ("POST", "PUT"):
            kwargs["data"] = self.request.POST
        return MeetingAnswersForm(**kwargs)

    def get_context_data(self, **kwargs):
        """Expose the meeting, student, and generated answer fields."""
        context = super().get_context_data(**kwargs)
        context.setdefault("answers_form", self.get_answers_form())
        context["meeting"] = self.get_meeting()
        context["student"] = self.get_access_student()
        return context

    def save_forms(self, form, answers_form):
        """Validate ownership fields and save the record and answers atomically."""
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.set_ownership(self.object)
                self.object.full_clean()
                self.object.save()
                answers_form.save(self.object)
        except ValidationError as error:
            form.add_error(None, ValidationError(error.messages))
            return self.form_invalid(form, answers_form)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, answers_form=None):
        """Render errors from both the attendance and answers forms."""
        return self.render_to_response(
            self.get_context_data(form=form, answers_form=answers_form or self.get_answers_form())
        )

    def get_success_url(self):
        """Show the saved record."""
        return reverse("tutorial:meeting-attendance-detail", kwargs={"pk": self.object.pk})


class MeetingAttendanceCreateView(TutorMeetingAccessMixin, MeetingRecordFormMixin, CreateView):
    """Create a meeting record for a student assigned to the current tutor."""

    def dispatch(self, request, *args, **kwargs):
        self.meeting = get_object_or_404(Meeting, pk=kwargs["meeting_pk"])
        self.student = get_object_or_404(Account, pk=kwargs["student_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_meeting(self):
        return self.meeting

    def get_access_student(self):
        return self.student

    def set_ownership(self, attendance):
        """Set fields that must never be accepted from posted form data."""
        attendance.meeting = self.meeting
        attendance.student = self.student
        attendance.staff = self.request.user

    def post(self, request, *args, **kwargs):
        """Validate the parent and all dynamic answers before saving either."""
        self.object = None
        form = self.get_form()
        answers_form = self.get_answers_form()
        if form.is_valid() and answers_form.is_valid():
            return self.save_forms(form, answers_form)
        return self.form_invalid(form, answers_form)


class MeetingAttendanceUpdateView(TutorMeetingAccessMixin, MeetingRecordFormMixin, UpdateView):
    """Update a meeting record belonging to the current tutor's student."""

    def get_queryset(self):
        return MeetingAttendance.objects.select_related("meeting", "student", "staff")

    def get_record(self):
        """Load and cache the record before the access mixin is evaluated."""
        if not hasattr(self, "object"):
            self.object = self.get_object()
        return self.object

    def get_meeting(self):
        return self.get_record().meeting

    def get_access_student(self):
        return self.get_record().student

    def set_ownership(self, attendance):
        """Refresh the recording staff member without accepting ownership from POST data."""
        attendance.staff = self.request.user

    def post(self, request, *args, **kwargs):
        """Validate the parent and all dynamic answers before saving either."""
        self.object = self.get_object()
        form = self.get_form()
        answers_form = self.get_answers_form()
        if form.is_valid() and answers_form.is_valid():
            return self.save_forms(form, answers_form)
        return self.form_invalid(form, answers_form)


class MeetingRecordReadAccessMixin(IsStudentViewixin):
    """Allow the student, their assigned tutor, or a superuser to read a record."""

    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        attendance = self.get_object()
        return (
            self.request.user.is_superuser
            or attendance.student_id == self.request.user.pk
            or (self.request.user.is_staff and tutor_for(attendance.student) == self.request.user)
        )


class MeetingAttendanceDetailView(MeetingRecordReadAccessMixin, DetailView):
    """Display one meeting record and its answers in template order."""

    model = MeetingAttendance
    context_object_name = "attendance"
    template_name = "tutorial/meetingattendance_detail.html"
    queryset = MeetingAttendance.objects.select_related("meeting", "meeting__module", "student", "staff")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        answers = {answer.question_id: answer for answer in self.object.answers.select_related("question")}
        context["responses"] = [
            (question, answers.get(question.pk)) for question in self.object.meeting.ordered_questions
        ]
        context["can_edit"] = self.request.user.is_superuser or (
            self.request.user.is_staff and tutor_for(self.object.student) == self.request.user
        )
        context["can_delete"] = self.request.user.is_superuser
        return context


class MeetingAttendanceDeleteView(IsSuperuserViewMixin, DeleteView):
    """Delete a meeting record; this operation is restricted to superusers."""

    model = MeetingAttendance
    context_object_name = "attendance"
    template_name = "tutorial/meetingattendance_confirm_delete.html"
    success_url = "/"
