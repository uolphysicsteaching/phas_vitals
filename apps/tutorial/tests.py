"""Tests for meeting templates and records."""

# Python imports
from datetime import date
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
from tutorial.views import MeetingAttendanceActionView, MeetingDetailView

# app imports
from .models import (
    Answer,
    Meeting,
    MeetingAttendance,
    MeetingQuestion,
    Question,
    Tutorial,
    TutorialAssignment,
)


class MeetingModelTests(TestCase):
    """Exercise the constraints and validation of the meeting domain model."""

    @classmethod
    def setUpTestData(cls):
        cls.level = Year.objects.create(name="Level 1", status="UG", level=1)
        cls.other_level = Year.objects.create(name="Level 2", status="UG", level=2)
        cls.staff = Account.objects.create_user(username="tutor", number=990001, is_staff=True)
        cls.student = Account.objects.create_user(username="student", number=990002, year=cls.level)
        cls.meeting = Meeting.objects.create(
            name="Initial review",
            level=cls.level,
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

    def test_meeting_name_is_unique_within_a_level(self):
        """Names may repeat between levels, but not inside one level."""
        Meeting.objects.create(name=self.meeting.name, level=self.other_level, due_semester=1, due_week=3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Meeting.objects.create(name=self.meeting.name, level=self.level, due_semester=2, due_week=4)

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

    def test_new_record_must_match_the_students_level(self):
        """A meeting record cannot be created for the wrong current level."""
        other_student = Account.objects.create_user(username="other-student", number=990003, year=self.other_level)
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
        cls.meeting = Meeting.objects.create(name="View test meeting", level=cls.level, due_semester=1, due_week=2)
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
        self.assertEqual(record.answers.get(question=self.question).data, {"text": "Good progress"})

    def test_non_tutor_and_superuser_cannot_create_record(self):
        for user in (self.other_staff, self.superuser):
            self.client.force_login(user)
            response = self.client.post(self.create_url(), {"status": MeetingAttendance.Status.IN_PERSON})
            self.assertEqual(response.status_code, 403)
        self.assertFalse(MeetingAttendance.objects.exists())

    def test_assigned_tutor_can_update_record_and_answers(self):
        record = self.make_record()
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
        self.assertEqual(record.answers.get().data, {"text": "Student did not attend"})

    def test_only_assigned_tutor_can_update(self):
        record = self.make_record()
        url = reverse("tutorial:meeting-attendance-update", kwargs={"pk": record.pk})
        for user in (self.other_staff, self.superuser, self.student):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_student_tutor_and_superuser_can_read(self):
        record = self.make_record()
        url = reverse("tutorial:meeting-attendance-detail", kwargs={"pk": record.pk})
        for user in (self.student, self.tutor, self.superuser):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 200)

        for user in (self.other_student, self.other_staff):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_meeting_detail_displays_notes_and_ordered_questions(self):
        second = Question.objects.create(type=Question.Type.YES_NO, text="Agreed?")
        MeetingQuestion.objects.create(meeting=self.meeting, question=second, position=2)
        request = RequestFactory().get(reverse("tutorial:meeting-detail", kwargs={"pk": self.meeting.pk}))
        request.user = self.student

        response = MeetingDetailView.as_view()(request, pk=self.meeting.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context_data["questions"]), [self.question, second])

    def test_student_cannot_read_meeting_for_another_level(self):
        other_level = Year.objects.create(name="View Level 2", status="UG", level=2)
        wrong_level_student = Account.objects.create_user(username="wrong-level", number=991006, year=other_level)
        wrong_level_student.groups.add(Group.objects.get(name="Student"))
        self.client.force_login(wrong_level_student)

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
        for user in (self.student, self.superuser):
            self.client.force_login(user)
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
    """Verify the Meetings dashboard partial and its level-specific rows."""

    @classmethod
    def setUpTestData(cls):
        cls.level = Year.objects.create(name="Summary Level", status="UG", level=1)
        other_level = Year.objects.create(name="Other Summary Level", status="UG", level=2)
        cls.student = Account.objects.create_user(username="summary-student", number=992001, year=cls.level)
        cls.cohort = Cohort.objects.create(name="202627")
        TermDate.objects.create(cohort=cls.cohort, week=1, start=date(2026, 8, 17))
        TermDate.objects.create(cohort=cls.cohort, week=14, start=date(2027, 1, 18))
        tutor = Account.objects.create_user(username="summary-tutor", number=992002, is_staff=True)
        tutorial = Tutorial.objects.create(code="SUMMARY-TEST", tutor=tutor, cohort=cls.cohort)
        TutorialAssignment.objects.create(tutorial=tutorial, student=cls.student)
        cls.later = Meeting.objects.create(name="Later", level=cls.level, due_semester=1, due_week=2)
        cls.earlier = Meeting.objects.create(name="Earlier", level=cls.level, due_semester=1, due_week=1)
        cls.future = Meeting.objects.create(name="Future", level=cls.level, due_semester=1, due_week=3)
        Meeting.objects.create(name="Different level", level=other_level, due_semester=1, due_week=1)

    def test_meetings_category_uses_its_dedicated_partial(self):
        view = StudentSummaryPageView()
        view.kwargs = {"category": "meetings"}

        self.assertEqual(view.get_template_names(), "accounts/parts/summary_meetings.html")

    def test_meeting_becomes_available_on_first_day_of_due_week(self):
        self.assertFalse(self.later.is_available_for(self.student, on_date=date(2026, 8, 23)))
        self.assertTrue(self.later.is_available_for(self.student, on_date=date(2026, 8, 24)))

    def test_meetings_context_is_level_specific_due_ordered_and_not_future(self):
        view = StudentSummaryPageView()
        view.kwargs = {"category": "meetings"}
        view.user = self.student
        view.request = RequestFactory().get("/")
        with patch("tutorial.models.tz.localdate", return_value=date(2026, 8, 30)):
            context = view.get_context_data_meetings()

        self.assertEqual(
            [row["meeting"] for row in context["meetings"]],
            [self.earlier, self.later],
        )

    def test_meetings_partial_links_to_template_and_attendance_views(self):
        html = render_to_string(
            "accounts/parts/summary_meetings.html",
            {
                "user": self.student,
                "meetings": [{"meeting": self.earlier, "attendance": None}],
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


class MeetingManagementViewTests(TestCase):
    """Exercise the superuser meeting editor and ordered inline questions."""

    @classmethod
    def setUpTestData(cls):
        cls.level = Year.objects.create(name="Management Level", status="UG", level=1)
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
            "level": "",
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

    def test_management_views_are_superuser_only(self):
        url = reverse("tutorial:meeting-manage-list")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_create_meeting_with_ordered_inline_questions(self):
        self.client.force_login(self.superuser)
        data = self.meeting_data(
            level=self.level.pk,
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
            level=self.level,
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
            level=self.level.pk,
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

        self.assertEqual(response.status_code, 302)
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
            level=self.level,
            due_semester=1,
            due_week=5,
        )
        question = Question.objects.create(type=Question.Type.TEXT, text="In use")
        MeetingQuestion.objects.create(meeting=meeting, question=question, position=1)
        self.client.force_login(self.superuser)

        response = self.client.post(reverse("tutorial:question-manage-delete", kwargs={"pk": question.pk}))

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Question.objects.filter(pk=question.pk).exists())
