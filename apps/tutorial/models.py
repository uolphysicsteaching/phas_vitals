# Python imports
"""Models for tutorial app."""
# Python imports
import logging
from datetime import timedelta
from typing import Dict, List, Optional, Tuple, Union

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DEFAULT_DB_ALIAS, models, transaction
from django.db.models import QuerySet
from django.utils import timezone as tz
from django.utils.functional import cached_property, classproperty
from django.utils.html import format_html, strip_tags
from django.utils.text import slugify

# external imports
import numpy as np
from accounts.models import (
    Account,
    Cohort,
    TermDate,
    Year,
    academic_Q,
    students_Q,
)
from constance import config
from minerva.models import Module, SummaryScore
from util.fields import ObfuscatedHTMLField
from util.models import colour, contrast, patch_model

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
    tutorial: "QuerySet[Tutorial]" = models.ForeignKey(
        "tutorial.Tutorial", on_delete=models.CASCADE, related_name="tutees"
    )
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
            student__in=self.students.filter(is_active=True),
            session__in=self.past_sessions,
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
            Attendance.objects.filter(
                student__in=self.students.filter(is_active=True),
                session__in=self.past_sessions,
            )
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
        "minerva.Module",
        on_delete=models.SET_NULL,
        related_name="tutorial_sessions",
        null=True,
        blank=True,
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
    @transaction.atomic
    def create_for_cohort(cls, cohort):
        """Create or update the standard teaching-week sessions for a cohort.

        Args:
            cohort (Cohort):
                The academic cohort for which sessions should be created.

        Returns:
            (tuple):
                The numbers of sessions created and updated.
        """
        schedule = []
        for semester, first_academic_week in ((1, 1), (2, 14)):
            for week in range(1, 12):
                academic_week = first_academic_week + week - 1
                try:
                    start = TermDate.reverse(cohort, academic_week, 0).date
                    end = TermDate.reverse(cohort, academic_week, 4).date
                except AttributeError as error:
                    raise ValueError(
                        f"No term-date mapping is available for {cohort}, semester {semester}."
                    ) from error
                schedule.append((semester, week, start, end))

        created_count = 0
        updated_count = 0
        for semester, week, start, end in schedule:
            _, created = cls.objects.update_or_create(
                cohort=cohort,
                semester=semester,
                name=f"Wk {week}",
                defaults={"week": week, "start": start, "end": end},
            )
            created_count += int(created)
            updated_count += int(not created)
        return created_count, updated_count

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
        Account,
        on_delete=models.CASCADE,
        limit_choices_to=students_Q,
        related_name="attendance",
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

    def save(
        self,
        force_insert=False,
        force_update=False,
        using=DEFAULT_DB_ALIAS,
        update_fields=None,
    ):  # pylint: disable=arguments-differ
        """Save the model and then signal to update the student's attendance reocrd."""
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
        for ss in self.student.summary_scores.filter(category__text="Tutorial"):
            ss.calculate()
            ss.save()


class Question(models.Model):
    """A reusable prompt included in one or more meeting templates."""

    class Type(models.TextChoices):
        """Supported answer types."""

        YES_NO = "yesno", "Yes/No"
        TEXT = "text", "Text"
        NUMBER = "number", "Number"
        SELECT = "select", "Single choice"
        MULTI_SELECT = "m-select", "Multiple choice"

    type = models.CharField(max_length=8, choices=Type.choices)
    text = ObfuscatedHTMLField()
    data = models.JSONField(default=list, blank=True)

    def clean(self):
        """Validate the choice metadata used by select questions."""
        super().clean()
        if self.type not in {self.Type.SELECT, self.Type.MULTI_SELECT}:
            return
        if not isinstance(self.data, list):
            raise ValidationError({"data": "Choices must be a list of [value, label] pairs."})
        values = []
        for choice in self.data:
            if not isinstance(choice, (list, tuple)) or len(choice) != 2:
                raise ValidationError({"data": "Each choice must be a [value, label] pair."})
            value, label = choice
            if not isinstance(value, str) or not isinstance(label, str):
                raise ValidationError({"data": "Choice values and labels must be strings."})
            values.append(value)
        if len(values) != len(set(values)):
            raise ValidationError({"data": "Choice values must be unique."})

    @property
    def choices(self):
        """Return choices in a form suitable for a Django form field."""
        return (
            [tuple(choice) for choice in self.data] if self.type in {self.Type.SELECT, self.Type.MULTI_SELECT} else []
        )

    def __str__(self):
        """Return a plain-text representation of the prompt."""
        return strip_tags(str(self.text))


class MeetingAttendanceManager(models.Manager):
    """Manager for MeetingAttendanceManager."""

    def get_by_natural_key(self, meeting, module, exam_code, student) -> "MeetingAttendance":
        """Find a record by its meeting, module and student identifiers."""
        return self.get(
            meeting__name=meeting,
            meeting__module__code=module,
            meeting__module__exam_code=exam_code,
            student__username=student,
        )


class MeetingAttendance(models.Model):
    """Records a student's attendance state and responses for a meeting."""

    class Status(models.TextChoices):
        """Possible attendance outcomes."""

        IN_PERSON = "in-person", "Attended in person"
        ONLINE = "online", "Attended online"
        NO_SHOW = "no-show", "Arranged but no show"
        NO_CONTACT = "no-contact", "No contact"

    objects = MeetingAttendanceManager()

    meeting: "models.ForeignKey[MeetingAttendance,Meeting]" = models.ForeignKey(
        "Meeting", on_delete=models.CASCADE, related_name="attendance_records"
    )
    student = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="meeting_records",
        limit_choices_to=students_Q,
    )
    staff = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="recorded_meetings",
        limit_choices_to=academic_Q,
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    flag = models.BooleanField(default=False, help_text="Mark this record for extra attention.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("meeting", "student"),
                name="unique_meeting_student",
            )
        ]

    def clean(self):
        """Require new records to belong to one of the student's modules."""
        super().clean()
        if (
            self._state.adding
            and self.meeting_id
            and self.student_id
            and not self.student.module_enrollments.filter(module_id=self.meeting.module_id).exists()
        ):
            raise ValidationError({"student": "The student is not enrolled on the meeting's module."})

    def natural_key(self) -> Tuple:
        """Use meeting name, module code and username as the natural key."""
        return (
            self.meeting.name,
            self.meeting.module.code,
            self.meeting.module.exam_code,
            self.student.username,
        )

    def __str__(self) -> str:
        """Create a string representation."""
        return (
            f"{self.meeting.name} - {self.student.display_name}: "
            f"{self.get_status_display()} ({self.staff.initials})"
        )


class Meeting(models.Model):
    """A module-specific meeting template containing ordered prompts."""

    name: "models.CharField" = models.CharField(max_length=40, unique=False)
    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        related_name="meetings",
        verbose_name="Module code",
    )
    notes: ObfuscatedHTMLField = ObfuscatedHTMLField(blank=True, default="")
    due_semester = models.PositiveSmallIntegerField(choices=settings.SEMESTERS)
    due_week = models.SmallIntegerField()
    questions = models.ManyToManyField(
        Question,
        through="MeetingQuestion",
        through_fields=("meeting", "question"),
        related_name="meetings",
        blank=True,
    )

    class Meta:
        ordering: Tuple = ("due_semester", "due_week", "name")
        constraints = [models.UniqueConstraint(fields=("name", "module"), name="unique_meeting_name_module")]

    def __str__(self) -> str:
        """Create a string representation."""
        return f"{self.name} - {self.module.code}"

    def is_for(self, student):
        """Return whether the student is enrolled on this meeting's module."""
        return student.module_enrollments.filter(module_id=self.module_id).exists()

    def first_day(self, cohort):
        """Return the first day of this meeting's due week for a cohort."""
        try:
            return TermDate.reverse_semester(cohort, self.due_semester, self.due_week).date
        except (AttributeError, ValueError):
            return None

    def is_available_for(self, student, on_date=None):
        """Return whether this meeting's due week has started for the student."""
        try:
            cohort = student.tutorial_group_assignment.tutorial.cohort
        except ObjectDoesNotExist:
            return False
        first_day = self.first_day(cohort) if cohort is not None else None
        return first_day is not None and (on_date or tz.localdate()) >= first_day

    @property
    def slug(self) -> str:
        """Create a slug for meething."""
        return slugify(self.name)

    @property
    def ordered_questions(self):
        """Return this template's prompts in their configured order."""
        return Question.objects.filter(meeting_links__meeting=self).order_by("meeting_links__position")


class MeetingQuestion(models.Model):
    """Place a reusable question at a stable position in a meeting template."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="question_links")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="meeting_links")
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ("meeting", "position")
        constraints = [
            models.UniqueConstraint(fields=("meeting", "question"), name="unique_question_per_meeting"),
            models.UniqueConstraint(
                fields=("meeting", "position"),
                name="unique_question_position_per_meeting",
            ),
        ]

    def __str__(self):
        """Identify the meeting, position and prompt."""
        return f"{self.meeting} #{self.position}: {self.question}"


class Answer(models.Model):
    """A typed response to one question in a submitted meeting record."""

    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="answers")
    attendance = models.ForeignKey(MeetingAttendance, on_delete=models.CASCADE, related_name="answers")
    data = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("question", "attendance"), name="unique_answer_per_question")]

    def clean(self):
        """Validate the stored JSON value against the question type and choices."""
        super().clean()
        if not self.question_id:
            return
        if self.attendance_id and not self.attendance.meeting.questions.filter(pk=self.question_id).exists():
            raise ValidationError({"question": "This question does not belong to the meeting template."})
        question_type = self.question.type
        if not isinstance(self.data, dict) or set(self.data) != {question_type}:
            raise ValidationError({"data": f"Answer data must contain only the '{question_type}' key."})
        value = self.data[question_type]
        if question_type == Question.Type.YES_NO and not isinstance(value, bool):
            raise ValidationError({"data": "A yes/no answer must be true or false."})
        if question_type == Question.Type.TEXT and not isinstance(value, str):
            raise ValidationError({"data": "A text answer must be a string."})
        if question_type == Question.Type.NUMBER and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValidationError({"data": "A number answer must be numeric."})
        allowed = {choice[0] for choice in self.question.choices}
        if question_type == Question.Type.SELECT and (not isinstance(value, str) or value not in allowed):
            raise ValidationError({"data": "The selected value is not configured for this question."})
        if question_type == Question.Type.MULTI_SELECT:
            if (
                not isinstance(value, list)
                or any(not isinstance(item, str) for item in value)
                or len(value) != len(set(value))
                or not set(value).issubset(allowed)
            ):
                raise ValidationError({"data": "All selected values must be unique configured choices."})

    @property
    def display_value(self):
        """Return a human-readable answer without marking stored HTML as safe."""
        value = self.data.get(self.question.type)
        labels = dict(self.question.choices)
        if self.question.type == Question.Type.YES_NO:
            return "Yes" if value else "No"
        if self.question.type == Question.Type.SELECT:
            return labels.get(value, value)
        if self.question.type == Question.Type.MULTI_SELECT:
            return list_join([labels.get(item, item) for item in value or []])
        return value

    def __str__(self):
        """Identify the response by student and prompt."""
        return f"{self.attendance.student.display_name}: {self.question}"


@patch_model(SummaryScore)
def calculate_tutorial(self):
    """Patch a function to create a summary score object for a VITALs."""
    data = {}
    colours = {}
    scores = self.student.engagement_scores()
    for (score, label, _), col in zip(
        settings.TUTORIAL_MARKS,
        ["silver", "tomato", "springgreen", "mediumseagreen", "forestgreen"],
    ):
        if count := scores[np.isclose(scores, score)].size:
            data[label] = count
            colours[label] = col
    self.data["data"] = data
    self.data["colours"] = colours
    try:
        record = (
            np.array(
                self.enrollment.student.tutorial_sessions.filter(session__cohort=self.student.cohort)
                .order_by("-session__start")
                .values_list("score")
            )
            .ravel()
            .astype(float)
        )
        if record.size > 0:
            record = np.where(record < 0, np.nan, record)
            record = np.where(record == 2, 3, record)  # Good and excellent engagement should count the same
            weight = np.exp(-np.arange(len(record)) / config.ENGAGEMENT_TC)
            perfect = (3 * np.ones_like(record) * weight)[~np.isnan(record)].sum()
            actual = (record * weight)[~np.isnan(record)].sum()
            result = np.round(100 * actual / perfect, 1)
        else:
            result = None

        self.score = result
    except (ValueError, ZeroDivisionError):
        self.score = None
    return self.score


@patch_model(Account, prep=property)
def engagement(self):
    """Get engagement score from Summary Score."""
    summary = np.array(self.summary_scores.filter(category__text="Tutorial").values_list("module__credits", "score"))
    summary = summary.astype(float)
    if summary.size == 0:
        return np.nan
    return float(np.nansum(np.nanprod(summary, axis=1)) / np.nansum(summary[:, 0]))


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
def tutorial_code(self) -> Optional[str]:
    """Return the cohort object of the students tutorial module."""
    try:
        return self.tutorial_group.last().code
    except (ObjectDoesNotExist, AttributeError):
        return None


@patch_model(Account, prep=property)
def engagement_colour(self) -> str:
    """Monkeypatch a routine to convert engagement scaore into a hex colour."""
    return colour(self.engagement)


@patch_model(Account)
def engagement_session(self, cohort=None, semester=None, sessions=None) -> dict:
    """Monkeypatch a method for getting the session engagement score."""
    if cohort is None:
        cohort: Cohort = self.cohort
    if semester is None:
        semester = 1 if tz.now().month >= 8 else 2
    if sessions is None:
        sessions = Session.objects.filter(cohort=cohort, semester=semester)
    sessions = list(sessions)
    enrolled_module_ids = set(self.module_enrollments.values_list("module_id", flat=True))
    eligible_sessions = [session for session in sessions if session.module_id in enrolled_module_ids]
    base = {session.pk: format_html("&nbsp;{}&nbsp;", "-") for session in eligible_sessions}
    for attendance in self.attendance.filter(type=SessionType.TUTORIAL, session__in=eligible_sessions):
        session = attendance.session
        if attendance.score is None:
            base[session.pk] = format_html("{}", " - ")
        else:
            score_imgs = [
                {"src": "/static/admin/img/icon-yes.svg", "alt": "Authorised Absence"},
                {"src": "/static/admin/img/icon-no.svg", "alt": "Unauthorised Absence"},
                {
                    "src": "/static/img/bronze_star.svg",
                    "alt": "Limited Engagement",
                    "width": 20,
                },
                {
                    "src": "/static/img/silver_star.svg",
                    "alt": "Good Engagement",
                    "width": 20,
                },
                {
                    "src": "/static/img/gold_star.svg",
                    "alt": "Outstanding Engagement",
                    "width": 20,
                },
            ]
            score = int(attendance.score) + 1
            image = score_imgs[score]
            if width := image.get("width"):
                base[session.pk] = format_html(
                    '<img src="{}" alt="{}" width="{}" />', image["src"], image["alt"], width
                )
            else:
                base[session.pk] = format_html('<img src="{}" alt="{}" />', image["src"], image["alt"])
    return base


@patch_model(Account)
def engagement_scores(self, cohort: Optional[Cohort] = None, semester: Optional[int] = None) -> float:
    """Monkeypatch a method for getting the session engagement score."""
    if cohort is None:
        cohort = self.cohort
    if semester is None:
        semester = 1 if tz.now().month >= 8 else 2
    ret = np.array(
        self.tutorial_sessions.filter(session__cohort=cohort).order_by("session__start").values_list("score")
    )[-11:]
    if ret.size == 0:
        return np.array([])
    return ret.T[0].astype(float)


@patch_model(Account, prep=property)
def engagement_label(self) -> str:
    """Monkey patched property for attendance ranking to a string."""
    translation = {
        "Excellent ": (90.0, 100.0),
        "Good": (60.0, 90.0),
        "Could be better": (40.0, 60.0),
        "Must Improve": (20.0, 40.0),
        "Unsatisfactory": (0, 20.0),
    }

    score = self.engagement
    if not isinstance(score, (float, int)):
        return "No Data"
    for name, (low, high) in translation.items():
        if low <= score <= high:
            return name
    return "Unknown"


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
