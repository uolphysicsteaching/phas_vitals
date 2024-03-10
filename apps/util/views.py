"""Views for the uil app - mainly mixin classes."""

# Django imports
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import TemplateView, View


# Create your views here.
class IsStudentViewixin(UserPassesTestMixin):
    """Provides a class that allows superusers,staff and students to login.

    IF the view.kwargs containst a username or a number then restrict the view to matching the username or
    number of the currently logged in user account.
    """

    login_url = "/login"

    def test_func(self):
        """Test if you a member of the correct group or have the staff/superuser flag set.

        If username is in self.kwargs, then the logged in username needs to match the username kwargs.
        """
        if not hasattr(self, "request") or self.request.user.is_anonymous:
            return False
        if (username := self.kwargs.get("username", None)) is not None:
            return self.request.user.is_staff or (
                self.request.user.is_member("Student") and self.request.user.username == username
            )
        if (number := self.kwargs.get("number", None)) is not None:
            return self.request.user.is_staff or (
                self.request.user.is_member("Student") and self.request.user.number == number
            )
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
    """Mixin class to ensure logged in user is a member of a particular group."""

    login_url = "/login"
    groups = []

    def get_groups(self):
        """Return a list of group names that the user should be a member of at least one."""
        if not isinstance(self.groups, (list, tuple)):
            groups = [self.groups]
        else:
            groups = self.groups
        return groups

    def test_func(self):
        """Test to see if the group given by get_group us one of the user's groups."""
        return hasattr(self, "request") and (self.request.user.groups.filter(name__in=self.get_groups()).count() > 0)


class SuperuserTemplateView(IsSuperuserViewMixin, TemplateView):
    """A template view that is restricted to superusers."""


class RedirectView(View):
    """Redirects the view to another class depending on the request user's attributes.

    is_superuser: self.get_superuser_view()->self.superuser_view
    is_staff: self.get_staff_view()->self.staff_view
    is_authenticated: selg.get_logged_in_view()->self.logged_in_view or self.anonymous_view
    group-map -> self.get_group_view()->self.group_map - find key that matches group.

    The first one that matches the condition and returns a non-None group is used to provide a dispatch method.
    """

    def get_superuser_view(self, request):
        """If the request user is a super user return superuser_view attribute or None."""
        if self.request.user.is_authenticated and self.request.user.is_superuser:
            return getattr(self, "superuser_view", None)
        return None

    def get_staff_view(self, request):
        """If the request user is a staff user return staff_view attribute or None."""
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return getattr(self, "staff_view", None)
        return None

    def get_logged_in_view(self, request):
        """If the request user is a super user return superuser_view attribute or None."""
        if self.request.user.is_authenticated:
            return getattr(self, "logged_in_view", None)
        return getattr(self, "anonymous_view", None)

    def get_group_view(self, request):
        """Get the mapping group_map and try to find a match to a group that the logged in user has."""
        if not self.request.user.is_authenticated:  # Not logged in, so no groups -> None
            return None
        groups = self.request.user.groups.all()
        for group, view in getattr(self, "group_map", {}).items():  # -> No group map -> no iteration
            if groups.filter(name=group).count() > 0:  # Group name in map -> return view
                return view
        return None  # Fall out of options

    def dispatch(self, request, *args, **kwargs):
        """Attempt to find another view to redirect to before calling super()."""
        for method in [self.get_superuser_view, self.get_staff_view, self.get_logged_in_view, self.get_group_view]:
            if view := method(request):
                return view.as_view()(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)
