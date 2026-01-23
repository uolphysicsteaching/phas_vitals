# -*- coding: utf-8 -*-
# Django imports
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q

# external imports
from ajax_select import LookupChannel, register

# app imports
from .models import Module, TestCategory


@register("testcategory")
class CategoryLookup(LookupChannel):
    """Lockup for Test Category Objects."""

    model = TestCategory
    parameter_name = "module"

    def get_query(self, q, request):
        """Query for test categories within a module.

        Args:
            q: The module primary key to filter on.
            request: The HTTP request object.

        Returns:
            (QuerySet): Test categories with test counts greater than zero.
        """
        name = Q(module__pk=q, in_dashboard=True)
        return self.model.objects.filter(name).annotate(count=Count("tests")).filter(count__gt=0)

    def format_item_display(self, item):
        """Format the display text for a test category.

        Args:
            item (TestCategory): The test category object.

        Returns:
            (str): The text representation of the category.
        """
        return item.text

    def format_match(self, item):
        """Format the value for matching a test category.

        Args:
            item (TestCategory): The test category object.

        Returns:
            (int): The primary key of the category.
        """
        return item.pk

    def check_auth(self, request):
        """Require a logged in user."""
        if not request.user.is_authenticated:
            raise PermissionDenied


@register("full_testcategory")
class FullCategoryLookup(LookupChannel):
    """Lockup for Test Category Objects in a module and sub-modules."""

    model = TestCategory
    parameter_name = "module"

    def get_query(self, q, request):
        """Query for test categories within a module and its sub-modules.

        Args:
            q: The module primary key to filter on.
            request: The HTTP request object.

        Returns:
            (QuerySet): Test categories from module and sub-modules with test counts.
        """
        name = Q(module__pk=q, in_dashboard=True)
        try:
            sub_modules = Module.objects.get(pk=q).sub_modules.all()
            name |= Q(module__in=sub_modules, in_dashboard=True)
        except Module.DoesNotExist:
            pass
        return self.model.objects.filter(name).annotate(count=Count("tests"))

    def format_item_display(self, item):
        """Format the display text for a test category.

        Args:
            item (TestCategory): The test category object.

        Returns:
            (str): The text representation of the category.
        """
        return item.text

    def format_match(self, item):
        """Format the value for matching a test category.

        Args:
            item (TestCategory): The test category object.

        Returns:
            (int): The primary key of the category.
        """
        return item.pk

    def check_auth(self, request):
        """Require a logged in user."""
        if not request.user.is_authenticated:
            raise PermissionDenied
