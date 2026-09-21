"""Tests for meeting templates and records."""

# Python imports
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

# Django imports
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

# external imports
from accounts.models import Account, Cohort, TermDate, Year
from accounts.views import StudentSummaryPageView
from minerva.models import Module, ModuleEnrollment, StatusCode
from tutorial.templatetags.tutorial_tags import engagement
from tutorial.views import (
    AdminEngagementSummaryView,
    MeetingAttendanceActionView,
    MeetingDetailView,
    SubmitStudentEngagementView,
    TutorStudentEngagementSummary,
)

# app imports
from .models import (
    Answer,
    Attendance,
    Meeting,
    MeetingAttendance,
    MeetingQuestion,
    Question,
    Session,
    Tutorial,
    TutorialAssignment,
)


class SessionModelTests(TestCase):
    """Test creation of standard cohort teaching sessions."""

    def test_create_for_cohort_builds_both_semesters(self):
        """Create weeks 1–11 with Monday-to-Friday dates in both semesters."""
        cohort = Cohort.objects.create(name="202627")
        TermDate.objects.create(cohort=cohort, week=1, start=date(2026, 9, 28))
        TermDate.objects.create(cohort=cohort, week=14, start=date(2027, 1, 25))

        created, updated = Session.create_for_cohort(cohort)

        self.assertEqual((created, updated), (22, 0))
        self.assertEqual(Session.objects.filter(cohort=cohort).count(), 22)
        self.assertEqual(
            Session.objects.get(cohort=cohort, semester=1, week=1, name="Wk 1").start,
            date(2026, 9, 28),
        )
        self.assertEqual(
            Session.objects.get(cohort=cohort, semester=1, week=11, name="Wk 11").end,
            date(2026, 12, 11),
        )
        self.assertEqual(
            Session.objects.get(cohort=cohort, semester=2, week=1, name="Wk 1").start,
            date(2027, 1, 25),
        )
        self.assertEqual(
            Session.objects.get(cohort=cohort, semester=2, week=11, name="Wk 11").end,
            date(2027, 4, 9),
        )

    def test_create_for_cohort_updates_existing_sessions(self):
        """Make repeated session creation idempotent and refresh existing dates."""
        cohort = Cohort.objects.create(name="202627")
        term_start = TermDate.objects.create(cohort=cohort, week=1, start=date(2026, 9, 28))
        TermDate.objects.create(cohort=cohort, week=14, start=date(2027, 1, 25))
        Session.create_for_cohort(cohort)
        term_start.start = date(2026, 10, 5)
        term_start.save()

        created, updated = Session.create_for_cohort(cohort)

        self.assertEqual((created, updated), (0, 22))
        self.assertEqual(Session.objects.filter(cohort=cohort).count(), 22)
        self.assertEqual(
            Session.objects.get(cohort=cohort, semester=1, week=1, name="Wk 1").start,
            date(2026, 10, 5),
        )

    def test_create_for_cohort_requires_term_dates(self):
        """Create no sessions when a cohort has no term-date mapping."""
        cohort = Cohort.objects.create(name="202627")

        with self.assertRaisesMessage(ValueError, "No term-date mapping"):
            Session.create_for_cohort(cohort)

        self.assertFalse(Session.objects.filter(cohort=cohort).exists())


class EngagementSessionModuleTests(TestCase):
    """Show and edit tutorial sessions only for enrolled students."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = Cohort.objects.create(name="202728")
        cls.tutor = Account.objects.create_user(username="module-tutor", number=993001, is_staff=True)
        cls.superuser = Account.objects.create_superuser(username="module-admin", number=993002, password="test")
        cls.first_student = Account.objects.create_user(username="module-student-1", number=993003)
        cls.second_student = Account.objects.create_user(username="module-student-2", number=993004)
        cls.group = Tutorial.objects.create(code="MODULE-TEST", tutor=cls.tutor, cohort=cls.cohort)
        TutorialAssignment.objects.create(tutorial=cls.group, student=cls.first_student)
        TutorialAssignment.objects.create(tutorial=cls.group, student=cls.second_student)
        cls.status = StatusCode.objects.create(code="RE")
        cls.first_module = Module.objects.create(
            uuid="tutorial-module-1",
            code="PHAS1000",
            name="First tutorial module",
            year=cls.cohort,
        )
        cls.second_module = Module.objects.create(
            uuid="tutorial-module-2",
            code="PHAS2000",
            name="Second tutorial module",
            year=cls.cohort,
        )
        cls.unused_module = Module.objects.create(
            uuid="tutorial-module-3",
            code="PHAS3000",
            name="Unused tutorial module",
            year=cls.cohort,
        )
        ModuleEnrollment.objects.create(module=cls.first_module, student=cls.first_student, status=cls.status)
        ModuleEnrollment.objects.create(module=cls.second_module, student=cls.second_student, status=cls.status)
        cls.first_session = Session.objects.create(
            name="Module 1 week",
            semester=1,
            cohort=cls.cohort,
            module=cls.first_module,
            week=1,
            start=date(2027, 9, 27),
            end=date(2027, 10, 1),
        )
        cls.second_session = Session.objects.create(
            name="Module 2 week",
            semester=1,
            cohort=cls.cohort,
            module=cls.second_module,
            week=1,
            start=date(2027, 9, 27),
            end=date(2027, 10, 1),
        )
        cls.unused_session = Session.objects.create(
            name="Unused week",
            semester=1,
            cohort=cls.cohort,
            module=cls.unused_module,
            week=1,
            start=date(2027, 9, 27),
            end=date(2027, 10, 1),
        )

    def get_context(self, view_class, user):
        """Build the engagement context for one tutorial group."""
        request = RequestFactory().get("/")
        request.user = user
        view = view_class()
        view.request = request
        view.kwargs = {"semester": 1, "cohort": self.cohort.name, "code": self.group.code}
        return view.get_context_data()

    def test_staff_and_superuser_views_show_modules_used_by_group_members(self):
        """Exclude session columns for modules with no enrolled group member."""
        for view_class, user in (
            (TutorStudentEngagementSummary, self.tutor),
            (AdminEngagementSummaryView, self.superuser),
        ):
            with self.subTest(view_class=view_class):
                sessions = list(self.get_context(view_class, user)["sessions"])
                self.assertEqual(sessions, [self.first_session, self.second_session])

    def test_student_row_only_enables_sessions_for_their_modules(self):
        """Keep table cells aligned while leaving unenrolled module sessions inert."""
        html = engagement(
            self.first_student,
            1,
            self.cohort,
            [self.first_session, self.second_session],
        )

        self.assertIn(f"session_{self.first_student.pk}_{self.first_session.pk}", html)
        self.assertNotIn(f"session_{self.first_student.pk}_{self.second_session.pk}", html)
        self.assertEqual(html.count("<td"), 2)

    def test_submission_only_creates_attendance_for_enrolled_students(self):
        """Do not create attendance records for group members outside the session module."""
        view = SubmitStudentEngagementView()
        view.request = RequestFactory().get("/")
        view.request.user = self.tutor
        view.kwargs = {"session": f"{self.group.pk}:{self.first_session.pk}"}

        queryset = view.get_queryset()

        self.assertEqual(list(queryset.values_list("student", flat=True)), [self.first_student.pk])
        self.assertFalse(Attendance.objects.filter(student=self.second_student, session=self.first_session).exists())


class MeetingModelTests(TestCase):
    """Exercise the constraints and validation of the meeting domain model."""

    @classmethod
    def setUpTestData(cls):
        cls.level = Year.objects.create(name="Level 1", status="UG", level=1)
        cls.cohort = Cohort.objects.create(name="209899")
        cls.module = Module.objects.create(uuid="meeting-module", code="PHAS1000", name="Tutorials", year=cls.cohort)
        cls.other_module = Module.objects.create(
            uuid="other-meeting-module", code="PHAS2000", name="Other tutorials", year=cls.cohort
        )
        cls.status = StatusCode.objects.create(code="RE")
        cls.staff = Account.objects.create_user(username="tutor", number=990001, is_staff=True)
        cls.student = Account.objects.create_user(username="student", number=990002, year=cls.level)
        ModuleEnrollment.objects.create(module=cls.module, student=cls.student, status=cls.status)
        cls.meeting = Meeting.objects.create(
            name="Initial review",
            module=cls.module,
            notes="Discuss progress",
            due_semester=1,
            due_week=3,
        )

    def test_questions_are_ordered_on_a_meeting(self):
        """The explicit through model controls presentation order."""
        second = Question.objects.create(type=Question.Type.TEXT, text="Second")
        first = Question.objects.create(type=Question.Type.YES_NO, text="First")
        MeetingQuestion.objects.create(meeting=self.meeting, question=second, position=2)
        MeetingQuestion.objects.create(meeting=self.meeting, question=first, position=1)

        self.assertEqual(
            list(self.meeting.ordered_questions.values_list("text", flat=True)),
            ["First", "Second"],
        )

    def test_meeting_name_is_unique_within_a_module(self):
        """Names may repeat between modules, but not inside one module."""
        Meeting.objects.create(name=self.meeting.name, module=self.other_module, due_semester=1, due_week=3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Meeting.objects.create(name=self.meeting.name, module=self.module, due_semester=2, due_week=4)

    def test_negative_due_week_is_valid_and_resolves_before_each_semester(self):
        """Measure negative meeting weeks backwards from each semester's week zero."""
        TermDate.objects.create(cohort=self.cohort, week=1, start=date(2098, 9, 29))
        TermDate.objects.create(cohort=self.cohort, week=14, start=date(2099, 1, 26))
        semester_one = Meeting(name="Before semester one", module=self.module, due_semester=1, due_week=-1)
        semester_two = Meeting(name="Before semester two", module=self.module, due_semester=2, due_week=-1)

        semester_one.full_clean()
        semester_two.full_clean()

        self.assertEqual(semester_one.first_day(self.cohort), date(2098, 9, 15))
        self.assertEqual(semester_two.first_day(self.cohort), date(2099, 1, 12))

    def test_one_record_is_allowed_per_meeting_and_student(self):
        """A student cannot submit the same meeting twice."""
        MeetingAttendance.objects.create(
            meeting=self.meeting,
            student=self.student,
            staff=self.staff,
            status=MeetingAttendance.Status.IN_PERSON,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MeetingAttendance.objects.create(
                meeting=self.meeting,
                student=self.student,
                staff=self.staff,
                status=MeetingAttendance.Status.ONLINE,
            )

    def test_new_record_requires_module_enrolment(self):
        """A meeting record cannot be created for a student outside the module."""
        other_student = Account.objects.create_user(username="other-student", number=990003, year=self.level)
        record = MeetingAttendance(
            meeting=self.meeting,
            student=other_student,
            staff=self.staff,
            status=MeetingAttendance.Status.NO_CONTACT,
        )

        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_attendance_status_is_required_and_restricted_to_known_values(self):
        """Attendance records accept only the four defined outcomes."""
        record = MeetingAttendance(
            meeting=self.meeting,
            student=self.student,
            staff=self.staff,
            status="unexpected",
        )

        with self.assertRaises(ValidationError):
            record.full_clean()

        self.assertEqual(
            {value for value, _ in MeetingAttendance.Status.choices},
            {"in-person", "online", "no-show", "no-contact"},
        )

    def test_attendance_flag_defaults_to_false_and_is_filterable(self):
        """Meeting records can be marked and queried for extra attention."""
        record = MeetingAttendance.objects.create(
            meeting=self.meeting,
            student=self.student,
            staff=self.staff,
            status=MeetingAttendance.Status.IN_PERSON,
        )
        self.assertFalse(record.flag)

        record.flag = True
        record.save(update_fields=("flag",))

        self.assertEqual(list(MeetingAttendance.objects.filter(flag=True)), [record])

    def test_select_question_requires_canonical_choices(self):
        """Select metadata is a list of unique string value/label pairs."""
        question = Question(type=Question.Type.SELECT, text="Status", data={"bad": "shape"})
        with self.assertRaises(ValidationError):
            question.full_clean()

        question.data = [["on-track", "On track"], ["delayed", "Delayed"]]
        question.full_clean()

    def test_answer_type_choices_and_membership_are_validated(self):
        """Answers match both their question type and their meeting template."""
        question = Question.objects.create(
            type=Question.Type.SELECT,
            text="Status",
            data=[["on-track", "On track"], ["delayed", "Delayed"]],
        )
        MeetingQuestion.objects.create(meeting=self.meeting, question=question, position=1)
        attendance = MeetingAttendance.objects.create(
            meeting=self.meeting,
            student=self.student,
            staff=self.staff,
            status=MeetingAttendance.Status.ONLINE,
        )
        answer = Answer(attendance=attendance, question=question, data={"select": "unknown"})
        with self.assertRaises(ValidationError):
            answer.full_clean()

        answer.data = {"select": "on-track"}
        answer.full_clean()
        answer.save()
        self.assertEqual(answer.display_value, "On track")

        unrelated = Question.objects.create(type=Question.Type.TEXT, text="Not on this meeting")
        with self.assertRaises(ValidationError):
            Answer(attendance=attendance, question=unrelated, data={"text": "No"}).full_clean()

    def test_only_one_answer_per_question_is_allowed(self):
        """Database constraints prevent duplicate answers."""
        question = Question.objects.create(type=Question.Type.YES_NO, text="Agreed?")
        MeetingQuestion.objects.create(meeting=self.meeting, question=question, position=1)
        attendance = MeetingAttendance.objects.create(
            meeting=self.meeting,
            student=self.student,
            staff=self.staff,
            status=MeetingAttendance.Status.NO_SHOW,
        )
        Answer.objects.create(attendance=attendance, question=question, data={"yesno": True})

        with self.assertRaises(IntegrityError), transaction.atomic():
            Answer.objects.create(attendance=attendance, question=question, data={"yesno": False})


class MeetingAttendanceViewTests(TestCase):
    """Verify the meeting CRUD workflow and its object-level permissions."""

    @classmethod
    def setUpTestData(cls):
        cls.level = Year.objects.create(name="Level 1", status="UG", level=1)
        cls.cohort = Cohort.objects.create(name="209900")
        TermDate.objects.create(cohort=cls.cohort, week=1, start=date(2020, 9, 28))
        TermDate.objects.create(cohort=cls.cohort, week=14, start=date(2021, 1, 25))
        cls.tutor = Account.objects.create_user(username="view-tutor", number=991001, password="test", is_staff=True)
        cls.other_staff = Account.objects.create_user(
            username="other-staff", number=991002, password="test", is_staff=True
        )
        cls.superuser = Account.objects.create_superuser(username="view-admin", number=991003, password="test")
        cls.student = Account.objects.create_user(
            username="view-student", number=991004, password="test", year=cls.level
        )
        cls.other_student = Account.objects.create_user(
            username="other-view-student",
            number=991005,
            password="test",
            year=cls.level,
        )
        student_group = Group.objects.create(name="Student")
        cls.student.groups.add(student_group)
        cls.other_student.groups.add(student_group)
        cls.tutorial = Tutorial.objects.create(code="VIEW-TEST", tutor=cls.tutor, cohort=cls.cohort)
        TutorialAssignment.objects.create(tutorial=cls.tutorial, student=cls.student)
        cls.module = Module.objects.create(
            uuid="view-meeting-module", code="PHAS1000", name="View tutorials", year=cls.cohort
        )
        cls.status = StatusCode.objects.create(code="RE")
        ModuleEnrollment.objects.create(module=cls.module, student=cls.student, status=cls.status)
        cls.meeting = Meeting.objects.create(name="View test meeting", module=cls.module, due_semester=1, due_week=2)
        cls.question = Question.objects.create(type=Question.Type.TEXT, text="Progress")
        MeetingQuestion.objects.create(meeting=cls.meeting, question=cls.question, position=1)

    def create_url(self):
        return reverse(
            "tutorial:meeting-attendance-create",
            kwargs={"meeting_pk": self.meeting.pk, "student_pk": self.student.pk},
        )

    def action_url(self):
        return reverse(
            "tutorial:meeting-attendance-action",
            kwargs={"meeting_pk": self.meeting.pk, "student_pk": self.student.pk},
        )

    def action_response(self, user):
        request = RequestFactory().get(self.action_url())
        request.user = user
        return MeetingAttendanceActionView.as_view()(request, meeting_pk=self.meeting.pk, student_pk=self.student.pk)

    def make_record(self):
        return MeetingAttendance.objects.create(
            meeting=self.meeting,
            student=self.student,
            staff=self.tutor,
            status=MeetingAttendance.Status.IN_PERSON,
        )

    def test_assigned_tutor_can_create_record_and_answers(self):
        self.client.force_login(self.tutor)
        response = self.client.post(
            self.create_url(),
            {
                "status": MeetingAttendance.Status.ONLINE,
                "flag": "on",
                f"question_{self.question.pk}": "Good progress",
            },
        )

        record = MeetingAttendance.objects.get(meeting=self.meeting, student=self.student)
        self.assertRedirects(
            response,
            reverse("tutorial:meeting-attendance-detail", kwargs={"pk": record.pk}),
            fetch_redirect_response=False,
        )
        self.assertEqual(record.status, MeetingAttendance.Status.ONLINE)
        self.assertTrue(record.flag)
        self.assertEqual(record.answers.get(question=self.question).data, {"text": "Good progress"})

    def test_non_tutor_cannot_create_record(self):
        self.client.force_login(self.other_staff)
        response = self.client.post(self.create_url(), {"status": MeetingAttendance.Status.IN_PERSON})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(MeetingAttendance.objects.exists())

    def test_superuser_can_create_record_from_action(self):
        """Send a superuser to the creation form when no record exists."""
        response = self.action_response(self.superuser)
        self.assertEqual(response.status_code, 200)
        self.assertIn("tutorial/meetingattendance_form.html", response.template_name)

        self.client.force_login(self.superuser)
        response = self.client.post(self.action_url(), {"status": MeetingAttendance.Status.IN_PERSON})

        record = MeetingAttendance.objects.get(meeting=self.meeting, student=self.student)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(record.staff, self.superuser)

    def test_tutor_cannot_create_record_after_module_enrolment_is_removed(self):
        """Reject a meeting that is no longer possible for the student."""
        self.student.module_enrollments.all().delete()
        self.client.force_login(self.tutor)

        response = self.client.post(self.create_url(), {"status": MeetingAttendance.Status.IN_PERSON})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(MeetingAttendance.objects.exists())

    def test_assigned_tutor_can_update_record_and_answers(self):
        record = self.make_record()
        record.flag = True
        record.save(update_fields=("flag",))
        self.client.force_login(self.tutor)
        response = self.client.post(
            reverse("tutorial:meeting-attendance-update", kwargs={"pk": record.pk}),
            {
                "status": MeetingAttendance.Status.NO_SHOW,
                f"question_{self.question.pk}": "Student did not attend",
            },
        )

        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, MeetingAttendance.Status.NO_SHOW)
        self.assertFalse(record.flag)
        self.assertEqual(record.answers.get().data, {"text": "Student did not attend"})

    def test_only_assigned_tutor_can_update(self):
        record = self.make_record()
        url = reverse("tutorial:meeting-attendance-update", kwargs={"pk": record.pk})
        for user in (self.other_staff, self.student):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_student_tutor_and_superuser_can_read(self):
        record = self.make_record()
        url = reverse("tutorial:meeting-attendance-detail", kwargs={"pk": record.pk})
        for user in (self.student, self.tutor, self.superuser):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 200)

        for user in (self.other_student, self.other_staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_meeting_record_links_to_student_meeting_dashboard(self):
        """Return from a meeting record to the student's Meeting tab."""
        record = self.make_record()
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("tutorial:meeting-attendance-detail", kwargs={"pk": record.pk}))

        dashboard_url = reverse("accounts:student_detail", kwargs={"number": self.student.number})
        self.assertContains(response, f'href="{dashboard_url}#meeting"')
        self.assertContains(response, 'class="btn btn-lg btn-secondary"')

    def test_meeting_detail_displays_notes_and_ordered_questions(self):
        second = Question.objects.create(type=Question.Type.YES_NO, text="Agreed?")
        MeetingQuestion.objects.create(meeting=self.meeting, question=second, position=2)
        request = RequestFactory().get(reverse("tutorial:meeting-detail", kwargs={"pk": self.meeting.pk}))
        request.user = self.student

        response = MeetingDetailView.as_view()(request, pk=self.meeting.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context_data["questions"]), [self.question, second])
        response.render()
        self.assertInHTML(
            '<a class="btn btn-lg btn-secondary" href="#" onclick="window.history.back(); return false;">'
            '<span class="bi bi-arrow-left-circle" aria-hidden="true"></span> Back</a>',
            response.content.decode(),
        )

    def test_question_sections_are_omitted_when_meeting_has_no_questions(self):
        """Hide question headings and placeholder text for an empty meeting."""
        meeting = Meeting.objects.create(name="No questions", module=self.module, due_semester=1, due_week=2)
        attendance = MeetingAttendance.objects.create(
            meeting=meeting,
            student=self.student,
            staff=self.tutor,
            status=MeetingAttendance.Status.IN_PERSON,
        )
        self.client.force_login(self.student)

        meeting_response = self.client.get(reverse("tutorial:meeting-detail", kwargs={"pk": meeting.pk}))
        attendance_response = self.client.get(
            reverse("tutorial:meeting-attendance-detail", kwargs={"pk": attendance.pk})
        )

        self.assertNotContains(meeting_response, "Questions")
        self.assertNotContains(attendance_response, "Responses")
        self.assertNotContains(meeting_response, "This meeting has no configured questions.")
        self.assertNotContains(attendance_response, "This meeting has no configured questions.")

    def test_student_cannot_read_meeting_for_another_module(self):
        unenrolled_student = Account.objects.create_user(username="unenrolled", number=991006, year=self.level)
        unenrolled_student.groups.add(Group.objects.get(name="Student"))
        self.client.force_login(unenrolled_student)

        response = self.client.get(reverse("tutorial:meeting-detail", kwargs={"pk": self.meeting.pk}))

        self.assertEqual(response.status_code, 403)

    def test_only_superuser_can_delete(self):
        record = self.make_record()
        url = reverse("tutorial:meeting-attendance-delete", kwargs={"pk": record.pk})
        self.client.force_login(self.tutor)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(MeetingAttendance.objects.filter(pk=record.pk).exists())

        self.client.force_login(self.superuser)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(MeetingAttendance.objects.filter(pk=record.pk).exists())

    def test_meeting_action_sends_tutor_to_create_or_update(self):
        response = self.action_response(self.tutor)
        self.assertEqual(response.status_code, 200)
        self.assertIn("tutorial/meetingattendance_form.html", response.template_name)

        record = self.make_record()
        response = self.action_response(self.tutor)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["object"], record)

    def test_meeting_action_sends_student_and_superuser_to_detail(self):
        record = self.make_record()
        for user in (self.student, self.superuser):
            response = self.action_response(user)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context_data["attendance"], record)

    def test_meeting_action_rejects_unrelated_users(self):
        for user in (self.other_student, self.other_staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.action_url()).status_code, 403)

    def test_meeting_action_has_no_read_target_before_record_exists(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.action_url()).status_code, 404)

    def test_future_meeting_cannot_be_created_or_updated(self):
        self.client.force_login(self.tutor)
        with patch("tutorial.models.tz.localdate", return_value=date(2019, 1, 1)):
            self.assertEqual(self.client.get(self.create_url()).status_code, 403)
            self.assertEqual(self.client.get(self.action_url()).status_code, 403)

            record = self.make_record()
            update_url = reverse("tutorial:meeting-attendance-update", kwargs={"pk": record.pk})
            self.assertEqual(self.client.get(update_url).status_code, 403)


class MeetingSummaryPageTests(TestCase):
    """Verify the Meeting dashboard partial and its module-specific rows."""

    @classmethod
    def setUpTestData(cls):
        cls.level = Year.objects.create(name="Summary Level", status="UG", level=1)
        cls.student = Account.objects.create_user(username="summary-student", number=992001, year=cls.level)
        cls.cohort = Cohort.objects.create(name="202627")
        TermDate.objects.create(cohort=cls.cohort, week=1, start=date(2026, 8, 17))
        TermDate.objects.create(cohort=cls.cohort, week=14, start=date(2027, 1, 18))
        tutor = Account.objects.create_user(username="summary-tutor", number=992002, is_staff=True)
        tutorial = Tutorial.objects.create(code="SUMMARY-TEST", tutor=tutor, cohort=cls.cohort)
        TutorialAssignment.objects.create(tutorial=tutorial, student=cls.student)
        cls.module = Module.objects.create(
            uuid="summary-meeting-module", code="PHAS1000", name="Summary tutorials", year=cls.cohort
        )
        other_module = Module.objects.create(
            uuid="other-summary-module", code="PHAS2000", name="Other summary", year=cls.cohort
        )
        status = StatusCode.objects.create(code="RE")
        ModuleEnrollment.objects.create(module=cls.module, student=cls.student, status=status)
        cls.later = Meeting.objects.create(name="Later", module=cls.module, due_semester=1, due_week=2)
        cls.earlier = Meeting.objects.create(name="Earlier", module=cls.module, due_semester=1, due_week=1)
        cls.future = Meeting.objects.create(name="Future", module=cls.module, due_semester=1, due_week=3)
        Meeting.objects.create(name="Different module", module=other_module, due_semester=1, due_week=1)

    def test_meeting_category_uses_its_dedicated_partial(self):
        view = StudentSummaryPageView()
        view.kwargs = {"category": "meeting"}
        view.request = RequestFactory().get("/")
        view.request.htmx = SimpleNamespace(trigger_name=None, trigger=None, target="meeting")

        self.assertEqual(view.get_template_names(), "accounts/parts/summary_meetings.html")
        self.assertEqual(view.get_context_data_function().__name__, "get_context_data_meeting")

    def test_meeting_becomes_available_on_first_day_of_due_week(self):
        self.assertFalse(self.later.is_available_for(self.student, on_date=date(2026, 8, 23)))
        self.assertTrue(self.later.is_available_for(self.student, on_date=date(2026, 8, 24)))

    def test_meeting_context_separates_available_and_future_meetings(self):
        view = StudentSummaryPageView()
        view.kwargs = {"category": "meeting"}
        view.user = self.student
        view.request = RequestFactory().get("/")
        with patch("accounts.views.tz.localdate", return_value=date(2026, 8, 30)):
            context = view.get_context_data_meeting()

        self.assertEqual(
            [row["meeting"] for row in context["meetings"]],
            [self.earlier, self.later],
        )
        self.assertEqual(context["future_meetings"], [self.future])

    def test_meeting_partial_links_to_template_and_attendance_views(self):
        html = render_to_string(
            "accounts/parts/summary_meetings.html",
            {
                "user": self.student,
                "meetings": [{"meeting": self.earlier, "attendance": None}],
                "future_meetings": [self.future],
            },
        )

        self.assertIn(reverse("tutorial:meeting-detail", kwargs={"pk": self.earlier.pk}), html)
        self.assertIn(
            reverse(
                "tutorial:meeting-attendance-action",
                kwargs={
                    "meeting_pk": self.earlier.pk,
                    "student_pk": self.student.pk,
                },
            ),
            html,
        )
        self.assertIn(reverse("tutorial:meeting-detail", kwargs={"pk": self.future.pk}), html)
        self.assertNotIn(
            reverse(
                "tutorial:meeting-attendance-action",
                kwargs={
                    "meeting_pk": self.future.pk,
                    "student_pk": self.student.pk,
                },
            ),
            html,
        )


class MeetingManagementViewTests(TestCase):
    """Exercise the superuser meeting editor and ordered inline questions."""

    @classmethod
    def setUpTestData(cls):
        cls.level = Year.objects.create(name="Management Level", status="UG", level=1)
        cls.cohort = Cohort.objects.create(name="209898")
        cls.module = Module.objects.create(
            uuid="management-meeting-module", code="PHAS1000", name="Management tutorials", year=cls.cohort
        )
        cls.superuser = Account.objects.create_superuser(username="management-admin", number=993001, password="test")
        cls.staff = Account.objects.create_user(
            username="management-staff",
            number=993002,
            password="test",
            is_staff=True,
        )

    @staticmethod
    def meeting_data(**extra):
        data = {
            "name": "Managed meeting",
            "module": "",
            "notes": "Agenda",
            "due_semester": 1,
            "due_week": 4,
            "questions-TOTAL_FORMS": 0,
            "questions-INITIAL_FORMS": 0,
            "questions-MIN_NUM_FORMS": 0,
            "questions-MAX_NUM_FORMS": 1000,
        }
        data.update(extra)
        return data

    def test_meeting_editor_has_no_blank_question_forms_by_default(self):
        """Do not add an unused question row to the meeting editor."""
        meeting = Meeting.objects.create(
            name="Meeting without questions",
            module=self.module,
            due_semester=1,
            due_week=4,
        )
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("tutorial:meeting-manage-update", kwargs={"pk": meeting.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context_data["question_formset"].forms), 0)

    def test_management_views_are_superuser_only(self):
        url = reverse("tutorial:meeting-manage-list")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_create_meeting_with_ordered_inline_questions(self):
        self.client.force_login(self.superuser)
        data = self.meeting_data(
            module=self.module.pk,
            **{
                "questions-TOTAL_FORMS": 2,
                "questions-0-text": "Second question",
                "questions-0-type": Question.Type.TEXT,
                "questions-0-data": "[]",
                "questions-0-ORDER": 2,
                "questions-1-text": "First question",
                "questions-1-type": Question.Type.YES_NO,
                "questions-1-data": "[]",
                "questions-1-ORDER": 1,
            },
        )

        response = self.client.post(reverse("tutorial:meeting-manage-create"), data)

        meeting = Meeting.objects.get(name="Managed meeting")
        self.assertRedirects(
            response,
            reverse("tutorial:meeting-manage-update", kwargs={"pk": meeting.pk}),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            list(meeting.ordered_questions.values_list("text", flat=True)),
            ["First question", "Second question"],
        )

    def test_update_reorders_and_inline_edits_questions(self):
        meeting = Meeting.objects.create(
            name="Managed meeting",
            module=self.module,
            notes="Agenda",
            due_semester=1,
            due_week=4,
        )
        first = Question.objects.create(type=Question.Type.TEXT, text="First")
        second = Question.objects.create(type=Question.Type.TEXT, text="Second")
        first_link = MeetingQuestion.objects.create(meeting=meeting, question=first, position=1)
        second_link = MeetingQuestion.objects.create(meeting=meeting, question=second, position=2)
        self.client.force_login(self.superuser)
        data = self.meeting_data(
            module=self.module.pk,
            **{
                "questions-TOTAL_FORMS": 2,
                "questions-INITIAL_FORMS": 2,
                "questions-0-id": first_link.pk,
                "questions-0-text": "First edited",
                "questions-0-type": Question.Type.TEXT,
                "questions-0-data": "[]",
                "questions-0-ORDER": 2,
                "questions-1-id": second_link.pk,
                "questions-1-text": "Second edited",
                "questions-1-type": Question.Type.TEXT,
                "questions-1-data": "[]",
                "questions-1-ORDER": 1,
            },
        )

        response = self.client.post(
            reverse("tutorial:meeting-manage-update", kwargs={"pk": meeting.pk}),
            data,
        )

        self.assertRedirects(
            response,
            reverse("tutorial:meeting-manage-list"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            list(meeting.ordered_questions.values_list("text", flat=True)),
            ["Second edited", "First edited"],
        )

    def test_question_crud_is_superuser_only(self):
        create_url = reverse("tutorial:question-manage-create")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(create_url).status_code, 403)

        self.client.force_login(self.superuser)
        response = self.client.post(
            create_url,
            {"text": "Standalone question", "type": Question.Type.TEXT, "data": "[]"},
        )
        self.assertRedirects(
            response,
            reverse("tutorial:question-manage-list"),
            fetch_redirect_response=False,
        )
        self.assertTrue(Question.objects.filter(text="Standalone question").exists())

    def test_linked_question_delete_is_reported_without_server_error(self):
        meeting = Meeting.objects.create(
            name="Protected question meeting",
            module=self.module,
            due_semester=1,
            due_week=5,
        )
        question = Question.objects.create(type=Question.Type.TEXT, text="In use")
        MeetingQuestion.objects.create(meeting=meeting, question=question, position=1)
        self.client.force_login(self.superuser)

        response = self.client.post(reverse("tutorial:question-manage-delete", kwargs={"pk": question.pk}))

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Question.objects.filter(pk=question.pk).exists())
