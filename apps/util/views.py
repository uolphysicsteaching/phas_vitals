# Django imports
from django.shortcuts import render
from django.contrib.auth.mixins import UserPassesTestMixin

# Create your views here.
class IsStudentViewixin(UserPassesTestMixin):
    login_url = "/login"

    def test_func(self):
        if not hasattr(self, "request") or self.request.user.is_anonymous:
            return False
        return self.request.user.is_staff or self.request.user.is_member("Student")


class IsStaffViewMixin(UserPassesTestMixin):

    """Mixin class to ensure logged in user is a staff user."""

    login_url = "/login"

    def test_func(self):
        return hasattr(self, "request") and (self.request.user.is_staff or self.request.user.is_superuser)


class IsSuperuserViewMixin(UserPassesTestMixin):

    """Mixin class to ensure logged in User is a Superuser account."""

    login_url = "/login"

    def test_func(self):
        return hasattr(self, "request") and self.request.user.is_superuser


class IsMemberViewMixin(UserPassesTestMixin):

    """Mixin class to ensure logged in user is a member of a particular group"""

    login_url = "/login"
    groups = []

    def get_groups(self):
        """Returns a list of group names that the user should be a member of at least one."""
        if not isinstance(self.groups, (list, tuple)):
            groups = [self.groups]
        else:
            groups = self.groups
        return groups

    def test_func(self):
        return hasattr(self, "request") and (self.request.user.groups.filter(name__in=self.get_groups()).count() > 0)
