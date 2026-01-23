# -*- coding: utf-8 -*-
# Django imports
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Q

# external imports
from ajax_select import LookupChannel, register

# app imports
from .models import Account, Section, academic_Q, students_Q, tutor_Q


@register("groups")
class GroupLookup(LookupChannel):
    """Lockup for Group Objects."""

    model = Group
    parameter_name = "name"

    def get_query(self, q, request):
        """Query for groups by name.

        Args:
            q (str): The search query string.
            request: The HTTP request object.

        Returns:
            (QuerySet): Groups matching the name query.
        """
        name = Q(name__istartswith=q)
        return self.model.objects.filter(name)

    def format_item_display(self, item):
        """Format the display text for a group.

        Args:
            item (Group): The group object.

        Returns:
            (str): The name of the group.
        """
        return item.name

    def format_match(self, item):
        """Format the value for matching a group.

        Args:
            item (Group): The group object.

        Returns:
            (str): The name of the group.
        """
        return item.name

    def check_auth(self, request):
        """Require a logged in user."""
        if not request.user.is_authenticated:
            raise PermissionDenied


@register("sections")
class SectionLookup(LookupChannel):
    """Lockup for Group Objects."""

    model = Section
    parameter_name = "name"

    def get_query(self, q, request):
        """Query for sections by name or code.

        Args:
            q (str): The search query string.
            request: The HTTP request object.

        Returns:
            (QuerySet): Sections matching the name or code query.
        """
        name = Q(name__icontains=q) | Q(code__istartswith=q)
        return self.model.objects.filter(name)

    def format_item_display(self, item):
        """Format the display text for a section.

        Args:
            item (Section): The section object.

        Returns:
            (str): The name of the section.
        """
        return item.name

    def format_match(self, item):
        """Format the value for matching a section.

        Args:
            item (Section): The section object.

        Returns:
            (str): The name of the section.
        """
        return item.name

    def check_auth(self, request):
        """Require a logged in user."""
        if not request.user.is_authenticated:
            raise PermissionDenied


@register("academic")
class AcademicAccountLookup(LookupChannel):
    """Lookup user accounts that are academic staff."""

    model = Account
    parameter_name = "name"

    def get_query(self, q, request):
        """Search on name,  username and email and limit to academic accounts."""
        username = Q(username__istartswith=q)
        name = Q(first_name__istartswith=q) | Q(last_name__istartswith=q)
        email = Q(email__istartswith=q)
        return self.model.objects.filter(academic_Q).filter(username | name | email)

    def format_item_display(self, item):
        """Format the display text for an account.

        Args:
            item (Account): The account object.

        Returns:
            (str): The display name of the account.
        """
        return item.display_name

    def format_match(self, item):
        """Format the value for matching an account.

        Args:
            item (Account): The account object.

        Returns:
            (str): The display name of the account.
        """
        return item.display_name

    def check_auth(self, request):
        """Require a logged in user."""
        if not request.user.is_authenticated:
            raise PermissionDenied


@register("tutor")
class TutorAccountLookup(AcademicAccountLookup):
    """Lookup tutor accounts - based on academic account lookup."""

    model = Account
    parameter_name = "name"

    def get_query(self, q, request):
        """Search on name,  username and email and limit to tutor accounts."""
        username = Q(username__istartswith=q)
        name = Q(first_name__istartswith=q) | Q(last_name__istartswith=q)
        email = Q(email__istartswith=q)
        return self.model.objects.filter(tutor_Q).filter(username | name | email)


@register("user")
class StudentAccountLookup(AcademicAccountLookup):
    """Lookup student accounts - based on academic account lookup."""

    model = Account
    parameter_name = "name"

    def get_query(self, q, request):
        """Search on name, username and email and limit to student accounts.

        Args:
            q (str): The search query string.
            request: The HTTP request object.

        Returns:
            (QuerySet): Student accounts matching the query.
        """
        username = Q(username__istartswith=q)
        name = Q(first_name__istartswith=q) | Q(last_name__istartswith=q)
        email = Q(email__istartswith=q)
        return self.model.objects.filter(students_Q).filter(username | name | email)
