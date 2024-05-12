# -*- coding: utf-8 -*-
"""Main site views."""
# Django imports
from django.views.generic import TemplateView

# external imports
from accounts.views import StudentSummaryView
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
