# -*- coding: utf-8 -*-
# Django imports
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q

# external imports
from ajax_select import LookupChannel, register

# app imports
from .models import TestCategory


@register("testcategory")
class CategoryLookup(LookupChannel):
    """Lockup for Test Category Objects."""

    model = TestCategory
    parameter_name = "module"

    def get_query(self, q, request):
        """Qyery on Group name only."""
        name = Q(module__pk=q, in_dashboard=True)
        return self.model.objects.filter(name).annotate(count=Count("tests")).filter(count__gt=0)

    def format_item_display(self, item):
        """Group name is the display text."""
        return item.text

    def format_match(self, item):
        """Match on Group.name."""
        return item.pk

    def check_auth(self, request):
        """Require a logged in user."""
        if not request.user.is_authenticated:
            raise PermissionDenied
