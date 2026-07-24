"""Linked-select endpoint backed by the optional django-ajax-selects package."""

# Django imports
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.views.generic import TemplateView

# app imports
from ._optional import get_ajax_select_registry

registry = get_ajax_select_registry()


class LinkedSelectEndpointView(TemplateView):
    """Return linked-select options from an authorised lookup."""

    http_method_names = ["get", "head", "options"]
    template_name = "htmx_views/widgets/options.html"

    def dispatch(self, request, *args, **kwargs):
        """Resolve the lookup and enforce its authorisation policy."""
        self.lookup_channel = kwargs.get("lookup_channel")
        try:
            self.lookup = registry.get(self.lookup_channel)
        except ImproperlyConfigured as error:
            raise Http404("Unknown linked-select lookup channel.") from error

        self.lookup.check_auth(request)
        self.parent = request.GET.get("_htmx_parent") or getattr(self.lookup, "parameter_name", None)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add the option list to the context."""
        if self.parent is None:
            raise ImproperlyConfigured(
                f"Creating an htmx_views widget for {self.lookup_channel} without knowing the trigger."
            )
        query = self.request.GET.get(self.parent)
        try:
            query = int(query)
        except (TypeError, ValueError):
            pass

        context = super().get_context_data(**kwargs)
        context["options"] = []
        if query:
            context["options"] = [
                (item.pk, str(item)) for item in self.lookup.get_query(query, self.request).distinct()
            ]
        return context
