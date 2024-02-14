# Django imports
from django.contrib.auth.mixins import UserPassesTestMixin


# Create your views here.
class IsStudentViewixin(UserPassesTestMixin):
    """Provides a class that allows superusers,staff and students to login."""

    login_url = "/login"

    def test_func(self):
        """Test if you a member of the correct group or have the staff/superuser flag set."""
        if not hasattr(self, "request") or self.request.user.is_anonymous:
            return False
        return self.request.user.is_staff or self.request.user.is_member("Student")


class IsStaffViewMixin(UserPassesTestMixin):

    """Mixin class to ensure logged in user is a staff user."""

    login_url = "/login"

    def test_func(self):
        """Test is either staff or superuser flag is set."""
        return hasattr(self, "request") and (self.request.user.is_staff or self.request.user.is_superuser)


class IsSuperuserViewMixin(UserPassesTestMixin):

    """Mixin class to ensure logged in User is a Superuser account."""

    login_url = "/login"

    def test_func(self):
        """Test if the superuser flag is set."""
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
        """Test to see if the group given by get_group us one of the user's groups."""
        return hasattr(self, "request") and (self.request.user.groups.filter(name__in=self.get_groups()).count() > 0)
