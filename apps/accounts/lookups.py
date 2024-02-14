# -*- coding: utf-8 -*-
# Django imports
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Q

# external imports
from ajax_select import LookupChannel, register

# app imports
from .models import Account, academic_Q, tutor_Q


@register("groups")
class GroupLookup(LookupChannel):

    """Lockup for Group Objects."""

    model = Group

    def get_query(self, q, request):
        """Qyery on Group name only."""
        name = Q(name__istartswith=q)
        return self.model.objects.filter(name)

    def format_item_display(self, item):
        """Group name is the display text."""
        return item.name

    def format_match(self, item):
        """Match on Group.name."""
        return item.name

    def check_auth(self, request):
        """Require a logged in user."""
        if not request.user.is_authenticated:
            raise PermissionDenied


@register("academic")
class AcademicAccountLookup(LookupChannel):
    """Lookup user accounts that are academic staff."""

    model = Account

    def get_query(self, q, request):
        """Search on name,  username and email and limit to academic accounts."""
        username = Q(username__istartswith=q)
        name = Q(first_name__istartswith=q) | Q(last_name__istartswith=q)
        email = Q(email__istartswith=q)
        return self.model.objects.filter(academic_Q).filter(username | name | email)

    def format_item_display(self, item):
        """Show dipsplay names."""
        return item.display_name

    def format_match(self, item):
        """Match on display names."""
        return item.display_name

    def check_auth(self, request):
        """Require a logged in user."""
        if not request.user.is_authenticated:
            raise PermissionDenied


@register("tutor")
class TutorAccountLookup(AcademicAccountLookup):
    """Lookip tutor accounts - based on academic account lookup."""

    model = Account

    def get_query(self, q, request):
        """Search on name,  username and email and limit to tutor accounts."""
        username = Q(username__istartswith=q)
        name = Q(first_name__istartswith=q) | Q(last_name__istartswith=q)
        email = Q(email__istartswith=q)
        return self.model.objects.filter(tutor_Q).filter(username | name | email)
