# Python imports
"""Models for tutorial app."""
# Python imports
import logging
from typing import Dict, List, Optional, Tuple, Union

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import DEFAULT_DB_ALIAS, models
from django.db.models import QuerySet
from django.utils import timezone as tz
from django.utils.functional import cached_property, classproperty
from django.utils.html import format_html
from django.utils.text import slugify

# external imports
import numpy as np
from accounts.models import Account, Cohort, academic_Q, students_Q
from constance import config
from tinymce.models import HTMLField
from util.models import colour, contrast, patch_model

# app imports
from phas_vitals import celery_app

update_engagement = celery_app.signature("accounts.tasks.update_engagement")
task_logger = logging.getLogger("celery_tasks")


def list_join(items, oxford=False):
    """Join string representations of the items together with commas and and as necessary."""
    if len(items) == 0:
        return ""
    elif len(items) == 1:
        return "{}".format(items[0])
    elif len(items) == 2:
        return "{} and {}".format(*items)
    else:
        last = " and {}".format(items[-1])
        first = ",".join(["{}".format(i) for i in items[:-1]])
        sep = "," if oxford else ""
        return "{}{}{}".format(first, sep, last)


# Create your models here.


class TutorialAssignmentManager(models.Manager):
    """Manager class for Tutorial Assignments."""

    def get_by_natural_key(self, tutorial, student):
        """Use a tuple of tutorial group code, student username as natural key."""
        return self.get(tutorial__code=tutorial, student__username=student)


class TutorialAssignment(models.Model):
    """A table to connect tutorials through to students and assessors."""

    objects = TutorialAssignmentManager()
    tutorial: "QuerySet[Tutorial]" = models.ForeignKey("Tutorial", on_delete=models.CASCADE, related_name="tutees")
    student: "models.OneToOneField[TutorialAssignment, Account]" = models.OneToOneField(
        Account,
        on_delete=models.CASCADE,
        related_name="tutorial_group_assignment",
        limit_choices_to=students_Q,
    )

    class Meta:
        unique_together = ["tutorial", "student"]

    def natural_key(self) -> Tuple:
        """Use a natural key od the tutorial group key and user name."""
        return (self.tutorial.code, self.student.username)

    def __str__(self) -> str:
        """Create string representation of student display name and tutor inisitals."""
        return f"{self.student.display_name} - {self.tutorial.tutor.initials}"


class TutorialManager(models.Manager):
    """Manager class for Tutorial group objects."""

    def get_by_natural_key(self, code) -> str:
        """Use the group code as the natual key."""
        return self.get(code=code)


class Tutorial(models.Model):
    """Defines a model tutorial item."""

    class Meta:
        ordering = ["code"]

    objects = TutorialManager()
    tutor: "models.ForeignKey[Tutorial, Account]" = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="tutor_groups",
        limit_choices_to=academic_Q,
        verbose_name="Tutor",
    )
    students: "models.ManyToManyField[Tutorial, Account]" = models.ManyToManyField(
        Account,
        related_name="tutorial_group",
        through=TutorialAssignment,
        through_fields=("tutorial", "student"),
    )
    cohort: "models.ForeignKey[Tutorial, Cohort]" = models.ForeignKey(
        Cohort,
        on_delete=models.SET_NULL,
        related_name="tutorial_groups",
        blank=True,
        null=True,
        verbose_name="Student cohort",
    )
    code: "models.CharField" = models.CharField(max_length=20, unique=True)

    def __str__(self) -> str:
        """Make a string representation."""
        if hasattr(self, "tutor"):
            return f"{self.code} ({self.tutor.initials})"
        return f"Group {self.pk}"

    @cached_property
    def numStudents(self) -> int:
        """Get the number of students in the tutorial group."""
        return self.students.filter(is_active=True).count()

    @property
    def members(self) -> "QuerySet[Tutorial]":
        """Sort the students but last name, first name."""
        return self.students.filter(is_active=True).order_by("last_name", "first_name")

    @property
    def past_sessions(self) -> "QuerySet[Session]":
        """Return the sessions for this group's cohort."""
        return Session.objects.filter(cohort=self.cohort, end__lt=tz.now())

    @property
    def missing_records(self) -> Dict[str, List[Account]]:
        """Build a dictionary of missing tutorial records."""
        if self.recorded_sessions == 1.0:  # No missing records
            return {}
        records = Attendance.objects.filter(
            student__in=self.students.filter(is_active=True), session__in=self.past_sessions
        ).exclude(score=None)
        students = self.members
        ret = {}
        for session in self.past_sessions:
            for student in students:
                if records.filter(student=student, session=session).count() == 0:
                    ret[str(session)] = ret.get(str(session), [])
                    ret[str(session)].append(student)
        return ret

    @property
    def recorded_sessions(self) -> float:
        """Return the the average number of sessions recorded per member of the tutorial group currently active."""
        if self.numStudents == 0:
            return 1.0
        return (
            Attendance.objects.filter(student__in=self.students.filter(is_active=True), session__in=self.past_sessions)
            .exclude(score=None)
            .count()
            / self.numStudents
        )

    @property
    def recorded(self) -> float:
        """Return the % of recorded sessions."""
        if (n := self.past_sessions.count()) > 0:
            return np.round(100 * self.recorded_sessions / n, 1)
        else:
            return 100.0

    @property
    def recorded_colour(self) -> str:
        """Turn the recording proportions into a colour scale."""
        return colour(100 * (self.recorded / 100.0) ** 2 / 1.01)

    @property
    def recorded_text_colour(self) -> str:
        """Get a contrasting colour for the recorded bg colour."""
        return contrast(self.recorded_colour)

    def natural_key(self) -> str:
        """Set the natural key as the group code."""
        return self.code


class Session(models.Model):
    """Represents a teaching session."""

    name: "models.CharField" = models.CharField(max_length=30)
    semester: "models.IntegerField" = models.IntegerField(default=0, choices=settings.SEMESTERS)
    cohort: "models.ForeignKey[Session,Cohort]" = models.ForeignKey(
        Cohort, on_delete=models.CASCADE, related_name="sessions"
    )
    module: "models.ForeignKey[minerva.Module]" = models.ForeignKey(
        "minerva.Module", on_delete=models.SET_NULL, related_name="tutorial_sessions", null=True, blank=True
    )

    week: "models.IntegerField" = models.IntegerField(default=0)
    start: "models.DateField" = models.DateField()
    end: "models.DateField" = models.DateField()

    class Meta:
        unique_together: Tuple = ("name", "semester", "cohort")
        ordering: Tuple = ("start",)

    def __str__(self) -> str:
        """Create a string representation."""
        return f"{self.name}-{settings.SEMESTERS[self.semester][1]} ({self.cohort})"

    @classmethod
    def past(cls, cohort=None):
        """Return all sessions that are in the past."""
        if cohort is not None:
            sessions = cls.objects.filter(cohort=cohort)
        else:
            sessions = cls.objects.all()
        return sessions.filter(end__lt=tz.now())

    @classmethod
    def future(cls, cohort=None):
        """Return all sessions that are in the past."""
        if cohort is not None:
            sessions = cls.objects.filter(cohort=cohort)
        else:
            sessions = cls.objects.all()
        return sessions.filter(start__gt=tz.now())

    @classmethod
    def current(cls, cohort=None):
        """Return all sessions that are in the past."""
        if cohort is not None:
            sessions = cls.objects.filter(cohort=cohort)
        else:
            sessions = cls.objects.all()
        return sessions.filter(start__lte=tz.now(), end__gte=tz.now())

    @property
    def stats(self):
        """Get some attendance set for this session."""
        attenances = self.attended_by.filter(student__is_active=True)
        potential = self.module.student_enrollments.filter(student__is_active=True).distinct().count()
        ret = {}
        for score, string, _ in settings.TUTORIAL_MARKS[1:]:
            ret[string] = attenances.filter(score=score).count()
        ret[settings.TUTORIAL_MARKS[0][1]] = attenances.filter(score__lt=0).count()
        ret["No Record"] = potential - sum([v for v in ret.values()])
        return ret

    @property
    def stats_legend(self):
        """Return a dictionary of items to use for the legend of a stats plot."""
        ret = {k: v for _, k, v in settings.TUTORIAL_MARKS}
        ret["No Record"] = "black"
        return ret


class SessionType(models.Model):
    """describes the type of attendance that a student might have at a session - e.g. tutorial or lab."""

    name: "models.CharField" = models.CharField(max_length=30, unique=True)
    description: "models.CharField" = models.CharField(max_length=120, null=True, blank=True)

    def __str__(self):
        """Use the name as a the natural key for the session."""
        return f"{self.name} Session"

    @classproperty
    def TUTORIAL(cls):
        """Make a Tutorial session."""
        return cls.objects.get_or_create(name="Tutorial")[0]

    @classproperty
    def LAB(cls):
        """Make a Lab sessions."""
        return cls.objects.get_or_create(name="Lab")[0]


class Attendance(models.Model):
    """Records Student attendance at a teaching session."""

    student: "models.ForeignKey[Attendance,Account]" = models.ForeignKey(
        Account, on_delete=models.CASCADE, limit_choices_to=students_Q, related_name="attendance"
    )
    session: "models.ForeignKey[Attendance,Session]" = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="attended_by"
    )
    type: "models.ForeignKey[Attendance,SessionType]" = models.ForeignKey(
        SessionType, on_delete=models.CASCADE, related_name="attended_by", null=True
    )

    score: "models.FloatField" = models.FloatField(
        choices=[(x, y) for x, y, _ in settings.TUTORIAL_MARKS], null=True, blank=True
    )

    class Meta:
        unique_together: Tuple = ("student", "session", "type")
        ordering: Tuple = ("student", "session")

    def __str__(self) -> str:
        """Make the string representation."""
        return f"{self.student.display_name} ({self.session}) ({getattr(self.type, 'name', '')} ): {self.score_str}"

    @property
    def score_str(self) -> str:
        """Return the session attendance score."""
        if self.score is None:
            return " - "
        if self.score < 0:  # needs special handling
            return settings.TUTORIAL_MARKS[0][1]
        for score, string, _ in settings.TUTORIAL_MARKS[1:]:
            if np.isclose(self.score, score):  # fp equality checks!
                return string
        return "Unknown !"

    @property
    def mark(self) -> Optional[float]:
        """Return the session score as a 0-100 mark."""
        if self.score is None:
            return None
        if self.score > 0:
            return self.score * 20 + 20.0
        elif self.score < 0:
            return np.nan
        else:
            return self.score

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        """Save the model and then signal to update the student's attendance reocrd."""
        super().save(force_insert, force_update, using, update_fields)
        task_logger.debug(f"Posting update user task for {self}")
        update_engagement.delay_on_commit(self.student.pk, True)


class MeetingAttendanceManager(models.Manager):
    """Manager for MeetingAttendanceManager."""

    def get_by_natural_key(self, meeting: "Meeting", student: Account) -> "MeetingAttendance":
        """Use a tuple of the meeting name and student username as the natural key."""
        return self.get(meeting__name=meeting, student__username=student)


class MeetingAttendance(models.Model):
    """Records that a student has attended a meeting."""

    objects = MeetingAttendanceManager()

    meeting: "models.ForeignKey[MeetingAttendance,Meeting]" = models.ForeignKey(
        "Meeting", on_delete=models.CASCADE, related_name="attendance_records"
    )
    student: "models.ForeignKey[MeetingAttendance,Account]" = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="meeting_records", limit_choices_to=students_Q
    )
    tutor: "models.ForeignKey[MeetingAttendance,Account]" = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="tutorial_meetings", limit_choices_to=academic_Q
    )
    submitted: "models.DateTimeField" = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together: Tuple = ("meeting", "student")

    def natural_key(self) -> Tuple:
        """Set the natural key as the meeting name and student username."""
        return (self.meeting.name, self.student.username)

    def __str__(self) -> str:
        """Create a string representation."""
        return f"{self.meeting.name} - {self.student.display_name} ({self.tutor.initials})"


class Meeting(models.Model):
    """Object for recording a meeting with a student."""

    name: "models.CharField" = models.CharField(max_length=40, unique=False)
    students: "models.ManyToManyField[Meeting,Account]" = models.ManyToManyField(
        Account, related_name="meetings", through=MeetingAttendance, through_fields=("meeting", "student")
    )
    cohort: "models.ForeignKey[Meeting,Cohort]" = models.ForeignKey(
        Cohort,
        on_delete=models.SET_NULL,
        related_name="meetings",
        blank=True,
        null=True,
        verbose_name="Student cohort",
    )
    notes: HTMLField = HTMLField(blank=True, default="")
    due_date: "models.DateField" = models.DateField(blank=True, null=True)

    class Meta:
        ordering: Tuple = ("due_date",)
        unique_together: Tuple = ("name", "cohort")

    def __str__(self) -> str:
        """Create a string representation."""
        return f"{self.name} - {self.cohort}"

    @property
    def slug(self) -> str:
        """Create a slug for meething."""
        return slugify(self.name)


@patch_model(Account, prep=property)
def tutorial_sessions(self):
    """Patch the user account model with a tutorial sessions property."""
    return self.attendance.filter(type=SessionType.TUTORIAL, session__cohort=self.cohort)


@patch_model(Account, prep=property)
def Tutorials_mark(self) -> Union[np.ndarray, float, None]:
    """Monkeypatched property for attendance ranking."""
    record = np.array(
        self.tutorial_sessions.filter(session__cohort=self.cohort).order_by("-session__start").values_list("score")
    )
    if record.size > 0:
        record = record[:, 0].astype(float)
    else:
        return 0.0
    record[record < 0] = np.nan
    ret = 33.33333 * np.nanmean(record)
    if np.isnan(ret):
        ret = None
    return ret


@patch_model(Account, prep=property)
def cohort(self) -> Optional[Cohort]:
    """Return the cohort object of the students tutorial module."""
    try:
        return self.module_enrollments.get(module__code=config.TUTORIAL_MODULE).module.year
    except ObjectDoesNotExist:
        return None


@patch_model(Account, prep=property)
def engagement_colour(self) -> str:
    """Monkeypatch a routine to convert engagement scaore into a hex colour."""
    return colour(self.engagement)


@patch_model(Account)
def engagement_session(self, cohort=None, semester=None) -> dict:
    """Monkeypatch a method for getting the session engagement score."""
    if cohort is None:
        cohort: Cohort = self.cohort
    if semester is None:
        semester = 1 if tz.now().month >= 8 else 2
    sessions: QuerySet[Session] = Session.objects.filter(cohort=cohort, semester=semester)
    base: format_html[int, str] = {x.pk: format_html("&nbsp;-&nbsp;") for x in sessions}
    for attendance in self.tutorial_sessions.filter(session__cohort=cohort, session__semester=semester):
        session = attendance.session
        if attendance.score is None:
            base[session.pk] = format_html(" - ")
        else:
            score_imgs = [
                {"src": "/static/admin/img/icon-yes.svg", "alt": "Authorised Absence"},
                {"src": "/static/admin/img/icon-no.svg", "alt": "Unauthorised Absence"},
                {"src": "/static/img/bronze_star.svg", "alt": "Limited Engagement", "width": 20},
                {"src": "/static/img/silver_star.svg", "alt": "Good Engagement", "width": 20},
                {"src": "/static/img/gold_star.svg", "alt": "Outstanding Engagement", "width": 20},
            ]
            score = int(attendance.score) + 1
            attrs = " ".join([f'{k}="{val}"' for k, val in score_imgs[score].items()])
            base[session.pk] = format_html(f"<img {attrs} />")
    return base


@patch_model(Account)
def engagement_scores(self, cohort: Optional[Cohort] = None, semester: Optional[int] = None) -> float:
    """Monkeypatch a method for getting the session engagement score."""
    if cohort is None:
        cohort = self.cohort
    if semester is None:
        semester = 1 if tz.now().month >= 8 else 2
    ret = np.array(
        self.tutorial_sessions.filter(session__cohort=cohort, session__semester=semester).values_list("score")
    )
    if ret.size == 0:
        return np.array([])
    return ret.T[0].astype(float)


@patch_model(Account)
def absence(self, cohort: Optional[Cohort] = None, semester: Optional[int] = None) -> float:
    """Calculate the proportion of absences."""
    if cohort is None:
        cohort = self.cohort
    if semester is None:
        semester = 1 if tz.now().month >= 8 else 2
    ret = self.engagement_scores(cohort, semester)
    if ret.size == 0:
        return 0.0
    absent = ret <= 0
    in_a_row = (absent & np.roll(absent, -1) & np.roll(absent, -2)).sum() * 33
    total = 100 * absent.sum() / max(3, absent.size)
    return min(in_a_row + total, 100.0)


@patch_model(Account, prep=property)
def number_tutees(self) -> QuerySet[Account]:
    """Return how many of students a tutor has."""
    return Account.students.filter(tutorial__tutor=self).count()
