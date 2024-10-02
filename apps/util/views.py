"""Views for the uil app - mainly mixin classes."""

# Django imports
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.views.generic import ListView, TemplateView, View
from django.views.generic.base import ContextMixin, TemplateResponseMixin
from django.views.generic.edit import FormMixin, ProcessFormView


# Create your views here.
class IsStudentViewixin(UserPassesTestMixin):
    """Provides a class that allows superusers,staff and students to login.

    IF the view.kwargs containst a username or a number then restrict the view to matching the username or
    number of the currently logged in user account.
    """

    login_url = settings.LOGIN_URL

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

    login_url = settings.LOGIN_URL

    def test_func(self):
        """Test is either staff or superuser flag is set."""
        return hasattr(self, "request") and (self.request.user.is_staff or self.request.user.is_superuser)


class IsSuperuserViewMixin(UserPassesTestMixin):
    """Mixin class to ensure logged in User is a Superuser account."""

    login_url = "/isteach/"

    def test_func(self):
        """Test if the superuser flag is set."""
        return hasattr(self, "request") and self.request.user.is_superuser


class IsMemberViewMixin(UserPassesTestMixin):
    """Mixin class to ensure logged in user is a member of a particular group."""

    login_url = settings.LOGIN_URL
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
        return self.get_anonymouys_view(request)

    def get_anonymouys_view(self, request):
        """Return the cntents of the anonymous_view."""
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
        self.kwargs.update(kwargs)
        kwargs = self.kwargs
        for method in [self.get_superuser_view, self.get_staff_view, self.get_logged_in_view, self.get_group_view]:
            if view := method(request):
                as_view_kwargs = getattr(self, "as_view_kwargs", {})
                return view.as_view(**as_view_kwargs)(request, *self.args, **self.kwargs)
        return super().dispatch(request, *self.args, **self.kwargs)


class MultiFormMixin(ContextMixin):
    """Mixin class that handles multiple forms within a view."""

    form_classes = {}
    prefixes = {}
    success_urls = {}
    grouped_forms = {}

    initial = {}
    prefix = None
    success_url = None
    forms_context_name = "forms"
    bind_data_methods = ["POST", "PUT"]

    def get_context_data(self, **kwargs):
        """Add previous cohorts tp the context in the correct prder."""
        context = super(MultiFormMixin, self).get_context_data(**kwargs)
        context[self.get_forms_context_name()] = self.get_forms(self.get_form_classes(), bind_all=True)
        return context

    def get_form_classes(self):
        """Return all the form classes when requested."""
        return self.form_classes

    def get_forms(self, form_classes, form_names=None, bind_all=False):
        """Return all the forms as a dictionary of forms."""
        return dict(
            [
                (key, self._create_form(key, klass, (form_names and key in form_names) or bind_all))
                for key, klass in form_classes.items()
            ]
        )

    def get_forms_context_name(self):
        """Return the context object name for the dictionary of forms."""
        return self.forms_context_name

    def get_form_kwargs(self, form_name, bind_form=False):
        """Build the form kwargs."""
        kwargs = {}
        kwargs.update({"initial": self.get_initial(form_name)})
        kwargs.update({"prefix": self.get_prefix(form_name)})

        if bind_form:
            kwargs.update(self._bind_form_data())

        return kwargs

    def forms_valid(self, forms, form_name):
        """Handle the case for valid forms returning the appropriate redirect."""
        form_valid_method = "%s_form_valid" % form_name
        if hasattr(self, form_valid_method):
            return getattr(self, form_valid_method)(forms[form_name])
        else:
            return HttpResponseRedirect(self.get_success_url(form_name))

    def forms_invalid(self, forms, form_name):
        """Handle the case for invalid forms returning the appropriate redirect."""
        form_invalid_method = "%s_form_invalid" % form_name
        if hasattr(self, form_invalid_method):
            return getattr(self, form_invalid_method)(forms[form_name])
        else:
            return self.render_to_response(self.get_context_data(forms=forms))

    def get_initial(self, form_name):
        """Return the initial values for the forms."""
        initial_method = f"get_{form_name}_initial"
        if hasattr(self, initial_method):
            return getattr(self, initial_method)()
        else:
            return self.initial.copy()

    def get_prefix(self, form_name):
        """Get a prefix for the elements of a form."""
        return self.prefixes.get(form_name, self.prefix)

    def get_success_url(self, form_name=None):
        """Return the url to redirect to on success."""
        return self.success_urls.get(form_name, self.success_url)

    def _create_form(self, form_name, klass, bind_form):
        """Generate a specific form."""
        form_kwargs = self.get_form_kwargs(form_name, bind_form)
        form_create_method = "create_%s_form" % form_name
        if hasattr(self, form_create_method):
            form = getattr(self, form_create_method)(**form_kwargs)
        else:
            form = klass(**form_kwargs)
        return form

    def _bind_form_data(self):
        """Attach the data to a form."""
        if self.request.method in ("POST", "PUT") and self.request.method in self.bind_data_methods:
            return {"data": self.request.POST, "files": self.request.FILES}
        if self.request.method in ("GET") and self.request.method in self.bind_data_methods:
            return {"data": self.request.GET, "files": self.request.FILES}
        return {}


class FormListView(FormMixin, ListView):
    """Provide a ListVIew with a form."""

    success_url = "/"  # Not actually used since we never redirect here

    @property
    def object_list(self):
        """Shim to make ListView work."""
        return self.get_queryset()

    @object_list.setter
    def object_list(self, valiue):
        """Do nothing since we're actually just an dummy for get_queryset."""

    def get(self, request, *args, **kwargs):
        """Handle GET requests and instantiates a blank version of the form before passing to ListView.get."""
        form_class = self.get_form_class()
        self.form = self.get_form(form_class)

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle POST requests.

        Instantiates a form instance with the passed POST variables and then checked for validity.
        Before going to ListView.get for rendering.
        """
        form_class = self.get_form_class()
        self.form = self.get_form(form_class)
        if (
            self.form.is_valid()
        ):  # Divert to the main listview get where we will override the context data and get_queryset
            self.form_valid(self.form)  # We call this to record form values but not to return anything.
            return super().get(request, *args, **kwargs)
        else:
            return self.form_invalid(self.form)  # Handle a bad form

    def get_context_data(self, **kwargs):
        """Call the parent get_context_data before adding the current form as context."""
        context = super().get_context_data(**kwargs)
        context["form"] = self.form
        return context


class ProcessMultipleFormsView(ProcessFormView):
    """Subclass of ProcessFormView to deal with multiple forms on a page."""

    def get(self, request, *args, **kwargs):
        """Handle GET requests."""
        form_classes = self.get_form_classes()
        forms = self.get_forms(form_classes)
        return self.render_to_response(self.get_context_data(forms=forms))

    def post(self, request, *args, **kwargs):
        """Handle POST requests."""
        form_classes = self.get_form_classes()
        form_name = request.POST.get("action")
        if self._individual_exists(form_name):
            return self._process_individual_form(form_name, form_classes)
        elif self._group_exists(form_name):
            return self._process_grouped_forms(form_name, form_classes)
        else:
            return self._process_all_forms(form_classes, form_name)

    def _individual_exists(self, form_name):
        """Check whether and individual form exists."""
        return form_name in self.form_classes

    def _group_exists(self, group_name):
        """Check whjether a group of form exists."""
        return group_name in self.grouped_forms

    def _process_individual_form(self, form_name, form_classes):
        """Handle one single form."""
        forms = self.get_forms(form_classes, (form_name,))
        form = forms.get(form_name)
        if not form:
            return HttpResponseForbidden()
        elif form.is_valid():
            return self.forms_valid(forms, form_name)
        else:
            return self.forms_invalid(forms, form_name)

    def _process_grouped_forms(self, group_name, form_classes):
        """Process a group of forms."""
        form_names = self.grouped_forms[group_name]
        forms = self.get_forms(form_classes, form_names)
        if all([forms.get(form_name).is_valid() for form_name in form_names.values()]):
            return self.forms_valid(forms)
        else:
            return self.forms_invalid(forms)

    def _process_all_forms(self, form_classes, form_name=None):
        """Process all forms that were submitted in a request."""
        forms = self.get_forms(form_classes, None, True)
        if all([form.is_valid() for form in forms.values()]):
            return self.forms_valid(forms, form_name)
        else:
            return self.forms_invalid(forms, form_name)


class BaseMultipleFormsView(MultiFormMixin, ProcessMultipleFormsView):
    """A base view for displaying several forms."""


class MultiFormsView(TemplateResponseMixin, BaseMultipleFormsView):
    """A view for displaying several forms, and rendering a template response."""
