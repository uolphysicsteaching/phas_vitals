"""Accounts app model classes."""

from __future__ import unicode_literals

# Python imports
import string

# Django imports
from django.contrib.auth.models import AbstractUser, Group, UserManager
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property, classproperty

# external imports
import numpy as np
from constance import config
from six import string_types
from util.models import colour
from util.validators import RangeValueValidator

# app imports
from . import names

# Some useful query objects

academic_Q = Q(groups__name="Instructor") | Q(is_staff=True)
tutor_Q = Q(groups__name="Grader") | Q(groups__name="Teaching Assistant") | Q(is_staff=True)
students_Q = Q(groups__name="Student")
markers_Q = models.Q(groups__name="Grader") | models.Q(is_staff=True) | models.Q(is_superuser=True)


DEGREE_LEVEL = [("B", "Bachelors"), ("MB", "Integrated Masters"), ("PGT", "Taught Masters"), ("O", "Other")]

LEVEL_OF_STUDY = [
    (-1, "Not a student"),
    (0, "Foundation Year"),
    (1, "First Year"),
    (2, "Second Year"),
    (3, "Third Yea"),
    (4, "Placement"),
    (5, "Masters"),
]


#### Model Classes #####################################################################################


class Cohort(models.Model):
    """Simple object to describe a cohort of students."""

    name = models.CharField(max_length=20, primary_key=True)

    class Meta:
        ordering = ["-name"]

    def __str__(self):
        """If cohort is an integer, assume it is of the form 20xxyy and convert to 20xx/yy."""
        try:
            return "{:.2f}".format(round(int(self.name) / 100, 2)).replace(".", "/")
        except ValueError:
            return self.name

    @classproperty
    def current(cls):
        """Try to return the Cohort for the current academic year."""
        return cls.new

    @classproperty
    def new(cls):
        """Try to return the Cohort for the current academic year."""
        date = timezone.now()
        year = date.year if date.month > 5 else date.year - 1
        y2 = year - 1999
        combined = str(year * 100 + y2)
        try:
            cohort, _ = cls.objects.get_or_create(name=combined)
            return cohort
        except (ObjectDoesNotExist, MultipleObjectsReturned):
            return None


class Programme(models.Model):
    """Represents a programme of study that a student might be on."""

    name = models.CharField(max_length=150, default="Unknown")
    code = models.CharField(max_length=15, primary_key=True)
    local = models.BooleanField(default=False, verbose_name="Parented by school")
    level = models.CharField(max_length=10, choices=DEGREE_LEVEL, verbose_name="Degree Level", null=True, blank=True)

    class Meta:
        ordering = [
            "name",
        ]

    def __str__(self):
        """Represent Programme by name and code."""
        return f"{self.name} ({self.code})"


class ActiveStudents(UserManager):
    """Provide a quick queryset directly to active student accounts."""

    def get_queryset(self):
        """Filter default queryset for non-staff, non-superuser, active only accounts."""
        return super().get_queryset().exclude(is_staff=True).exclude(is_superuser=True).exclude(is_active=False)


class Account(AbstractUser):
    """Custom user class that has information about student registrations, programmes etc."""

    class Meta:
        ordering = ["last_name", "first_name"]
        permissions = [("has_local", "Also has a local account"), ("is_local", "Is a local account")]
        indexes = [
            models.Index(fields=["number"]),
            models.Index(fields=["username"]),
        ]

    USERNAME_FIELD = "username"

    # Managers
    objects = UserManager()
    students = ActiveStudents()

    number = models.IntegerField(unique=True)
    title = models.CharField(max_length=20, blank=True, null=True)
    programme = models.ForeignKey(Programme, on_delete=models.SET_NULL, blank=True, null=True, related_name="students")
    level = models.IntegerField(
        default=1,
        verbose_name="Current Level of Study",
        choices=LEVEL_OF_STUDY,
    )
    givenName = models.CharField(max_length=128, blank=True, null=True, verbose_name="MS account given name")
    registration_status = models.CharField(max_length=10, blank=True, null=True, default="")
    section = models.ForeignKey("Section", on_delete=models.SET_NULL, blank=True, null=True, related_name="students")
    # Fields updated by celery tasks
    tests_score = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])
    labs_score = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])
    coding_score = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])
    vitals_score = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])
    engagement = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])
    activity_score = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])

    def natural_key(self):
        """Use the username as a natural key."""
        return self.username

    @property
    def display_name(self):
        """Display name is what we commonly use for lists of account objects."""
        if self.givenName and self.givenName != self.first_name:
            first_name = f"{self.givenName} ({self.first_name})"
        else:
            first_name = self.first_name
        last_name = self.last_name
        if config.SHOWCASE_MODE:
            first_name = names.first_names[self.number % len(names.first_names)]
            last_name = names.last_names[self.number % len(names.last_names)]
        return f"{last_name},{first_name}"

    @property
    def friendly_name(self):
        """A display name that is student facing."""
        if self.givenName and self.givenName != self.first_name:
            first_name = self.givenName
        else:
            first_name = self.first_name
        last_name = self.last_name
        if config.SHOWCASE_MODE:
            first_name = names.first_names[self.number % len(names.first_names)]
            last_name = names.last_names[self.number % len(names.last_names)]
        return f"{first_name} {last_name}"

    @property
    def apt(self):
        """Property to get to the APT."""
        if self.tutorial_group.count() > 0:
            return self.tutorial_group.order_by("cohort__name").last().tutor
        return None

    @property
    def formal_name(self):
        """Formal Name is used for referring to a specific single user."""
        if self.title is None or self.title == "":
            title = ""
        else:
            title = self.title
        initials = ".".join([x for x in self.initials][:-1])
        last_name = names.last_names[self.number % len(names.last_names)] if config.SHOWCASE_MODE else self.last_name
        return f"{title} {initials} {last_name}".strip()

    def __str__(self):
        """Show a standard representation of displayname + username."""
        return f"{self.display_name} ({self.username})"

    def is_member(self, group):
        """Test whether user is a member of a given group."""
        if not self.pk:
            return False
        if isinstance(group, string_types):
            return self.groups.filter(name=group).count() == 1
        elif isinstance(group, Group):
            return self.groups.filter(name=group.name).count() == 1
        else:
            return False

    @property
    def initials(self):
        """Generate a set of initials from either email or name."""
        if "." in self.email.split("@")[0]:
            userfield = self.email.split("@")[0]
            initials = [x.upper()[0] for x in userfield.split(".") if x[0] in string.ascii_letters]
            initials = "".join(initials)
        else:
            name = self.friendly_name
            initials = "".join([char[0] for char in name.split(" ")])
        if len(initials) > 1:
            return initials
        return self.username

    @property
    def nice_email(self):
        return f"{self.formal_name}<{self.email}>"

    @property
    def SID(self):
        """Return studnet number or obfuscated stiudent number in showcase mode."""
        if config.SHOWCASE_MODE:
            digits = np.sum([int(x) for x in str(self.number)])
            return self.number - digits
        return self.number

    @property
    def activity_label(self) -> str:
        """Monkey patched property for attendance ranking to a string."""
        translation = {
            "Excellent ": (90.0, 100.0),
            "Good": (60.0, 90.0),
            "Could be better": (40.0, 60.0),
            "Must Improve": (20.0, 40.0),
            "Unsatisfactory": (0, 20.0),
        }

        score = self.activity_score
        if not isinstance(score, (float, int)):
            return "No Data"
        for name, (low, high) in translation.items():
            if low <= score <= high:
                return name
        return "Unknown"

    @property
    def activity_colour(self) -> str:
        """Monkeypatch a routine to convert engagement scaore into a hex colour."""
        return colour(self.activity_score)

    @property
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

    @property
    def lab_engagement_label(self) -> str:
        """Monkey patched property for attendance ranking to a string."""
        translation = {
            "No Issues": (60.0, 100.0),
            "Could be better": (40.0, 60.0),
            "Must Improve": (20.0, 40.0),
            "Unsatisfactory": (0, 20.0),
        }

        score = self.lab_engagement
        if not isinstance(score, (float, int)):
            return "No Data"
        for name, (low, high) in translation.items():
            if low <= score <= high:
                return name
        return "Unknown"


class Section(models.Model):
    """Represent a student's lab groups for managing Gradescope."""

    name = models.CharField(max_length=150, default="Unknown", unique=True)
    group_code = models.CharField(max_length=150, default="", verbose_name="Minerva Group Code")
    group_set = models.CharField(max_length=150, default="", verbose_name="Minerva Group Set")
    self_enrol = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AccountGroup(Group):
    """A Proxy model to allow group admin in the correct app."""

    class Meta:
        proxy = True
        permissions = [("access_backend", "Backend_user_account")]
