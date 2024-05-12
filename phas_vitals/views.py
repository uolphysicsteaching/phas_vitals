# -*- coding: utf-8 -*-
"""Main site views."""
# Python imports
import sys

# Django imports
from django.utils.decorators import classonlymethod
from django.views.debug import technical_500_response
from django.views.generic import TemplateView

# external imports
from accounts.views import StudentSummaryView
from constance import config
from minerva.views import ShowAllTestResultsViiew
from tutorial.views import TutorStudentEngagementSummary
from util.views import RedirectView


class HomeView(RedirectView):
    """Decide what to do with the home url."""

    def get_anonymouys_view(self, request):
        """Set the template kwag."""
        if not hasattr(self, "as_view_kwargs"):
            self.as_view_kwargs = {}
        self.as_view_kwargs["template_name"] = "home.html"
        return TemplateView

    def get_logged_in_view(self, request):
        """Patch in the kwargs with the user number."""
        if self.request.user.is_authenticated:
            self.kwargs["username"] = request.user.username
            return StudentSummaryView
        return super().get_logged_in_view(request)

    superuser_view = ShowAllTestResultsViiew
    staff_view = TutorStudentEngagementSummary


class ErrorView(TemplateView):
    """Ensure we return an error code in our responses."""

    def get_error_code(self):
        """Crazy little hack !."""
        name = self.__class__.__name__
        return int(name[1:4])

    def get_context_date(self, **kwargs):
        """Get some common context data for the error view."""
        context = super().get_context_date(**kwargs)
        context["request"] = self.request
        context["user"] = self.request.user
        context["config"] = config
        return context

    def get_template_names(self):
        """Return a default template name."""
        return f"errors/{self.error_code}View.html"

    def render_to_response(self, context, **response_kwargs):
        """Render the error response."""
        response = super().render_to_response(context, **response_kwargs)
        response.status_code = self.get_error_code()
        return response


class E400View(ErrorView):
    """Call a custom 404 error page in the standard template."""


class E404View(ErrorView):
    """Call a custom 404 error page in the standard template."""


class E403View(ErrorView):
    """Call a custom 404 error page in the standard template."""


class E500View(ErrorView):
    """Call a custom 500 error page in the standard template."""

    @classonlymethod
    def as_view(cls, **initkwargs):
        """Respond to a request-response process."""
        for key in initkwargs:
            if key in cls.http_method_names:
                raise TypeError(
                    "The method name %s is not accepted as a keyword argument " "to %s()." % (key, cls.__name__)
                )
            if not hasattr(cls, key):
                raise TypeError(
                    f"{cls.__name__}() received an invalid keyword {key}. as_view only accepts arguments that are"
                    " already attributes of the class."
                )

        def view(request, *args, **kwargs):
            """Handle the actual view request."""
            self = cls(**initkwargs)
            self.setup(request, *args, **kwargs)
            if not hasattr(self, "request"):
                raise AttributeError(
                    "%s instance has no 'request' attribute. Did you override "
                    "setup() and forget to call super()?" % cls.__name__
                )
            return self.dispatch(request, *args, **kwargs)

        view.view_class = cls
        view.view_initkwargs = initkwargs
        # take name and docstring from class
        view.__doc__ = cls.__doc__
        view.__module__ = cls.__module__
        view.__annotations__ = cls.dispatch.__annotations__
        # Copy possible attributes set by decorators, e.g. @csrf_exempt, from
        # the dispatch method.
        view.__dict__.update(cls.dispatch.__dict__)
        return view

    def get(self, request, *args, **kwargs):
        """Respond to GET requests."""
        if request.user.is_superuser:
            return technical_500_response(request, *sys.exc_info())
        else:
            return super().get(request, *args, **kwargs)
