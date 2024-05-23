"""Accounts app model classes."""
from __future__ import unicode_literals

# Django imports
from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property, classproperty

# external imports
from six import string_types
from util.validators import RangeValueValidator

# Some useful query objects

academic_Q = Q(groups__name="Instructor") | Q(is_staff=True)
tutor_Q = Q(groups__name="Grader") | Q(groups__name="Teaching Assistant") | Q(is_staff=True)
students_Q = Q(groups__name="Student")
markers_Q = models.Q(groups__name="Grader") | models.Q(is_staff=True) | models.Q(is_superuser=True)


def update_new_user(user):
    """If a new user is a student and not a member of a cohort, assign them to the current cohort."""
    if not user.cohort and not (user.is_staff or user.is_superuser):
        cohort, _ = Cohort.current
        user.cohort = cohort
    return user


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


class Account(AbstractUser):
    """Custom user class that has information about student registrations, programmes etc."""

    class Meta:
        ordering = ["last_name", "first_name"]

    USERNAME_FIELD = "username"

    number = models.IntegerField(blank=True, null=True)
    title = models.CharField(max_length=20, blank=True, null=True)
    cohort = models.ForeignKey(Cohort, on_delete=models.SET_NULL, related_name="students", blank=True, null=True)
    programme = models.ForeignKey(Programme, on_delete=models.SET_NULL, blank=True, null=True, related_name="students")
    level = models.IntegerField(
        default=1,
        verbose_name="Current Level of Study",
        choices=LEVEL_OF_STUDY,
    )
    registration_status = models.CharField(max_length=10, blank=True, null=True, default="")
    # Fields updated by celery tasks
    tests_score = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])
    labs_score = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])
    vitals_score = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])
    engagement = models.FloatField(editable=False, null=True, validators=[RangeValueValidator((0.0, 100.0))])

    def natural_key(self):
        """Use the username as a natural key."""
        return self.username

    @cached_property
    def display_name(self):
        """Display name is what we commonly use for lists of account objects."""
        return f"{self.last_name},{self.first_name}"

    @cached_property
    def apt(self):
        """Property to get to the APT."""
        if self.tutorial_group:
            return self.tutorial_group.first().tutor
        return None

    @cached_property
    def formal_name(self):
        """Formal Name is used for referring to a specific single user."""
        if self.title is None:
            title = ""
        else:
            title = self.title
        initials = [x for x in self.initials]
        initials = ".".join(initials[:-1])
        return f"{title} {initials} {self.last_name}".strip()

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

    @cached_property
    def initials(self):
        """Generate a set of initials from either email or name."""
        if "." in self.email:
            userfield = self.email.split("@")[0]
            initials = [x.upper()[0] for x in userfield.split(".")]
            initials = "".join(initials)
        else:
            initials = (self.first_name + "?")[0].upper() + (self.last_name + "?")[0].upper()
        if len(initials) > 1:
            return initials
        else:
            return self.username


class AccountGroup(Group):
    """A Proxy model to allow group admin in the correct app."""

    class Meta:
        proxy = True
