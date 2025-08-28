# -*- coding: utf-8 -*-
"""Create an htmx backed linked select widget."""

# Django imports
from django.core.exceptions import ImproperlyConfigured
from django.forms import ModelChoiceField
from django.forms.widgets import Select
from django.urls import reverse, reverse_lazy

# external imports
from ajax_select import registry


class HTMXSelectWidget(Select):
    """Override SelectWidget to allow the options to be updated on a linked change.

    This uses the machinery of django-ajax-select lookups to derive the list of options,
    but uses htmx for the transfer mechanism.
    """

    # temmplate_name = "htmx_views/widgets/select.html"

    def __init__(self, lookup_channel, parent=None, *args, **kargs):
        """Extract linked Select.

        Args:
            lookup_channel (str):
                The name of an ajax_select lookup channel
        """
        try:
            self.lookup_class = registry.get(lookup_channel)
        except ImproperlyConfigured:
            raise ImproperlyConfigured(
                f"Attempting to use a htmx_views widget with lookup channel {lookup_channel} that does not exist."
            )

        self.lookup_channel = lookup_channel
        if parent is None:
            parent = getattr(self.lookup, "paramater_name", None)
        if parent is None:
            raise ImproperlyConfigured(
                f"Creating an htmx_views widget for {lookup_channel} without knowing the trigger."
            )
        self.parent_name = parent
        attrs = kargs.pop("attrs", {})
        attrs.update(
            {
                "hx-get": reverse_lazy("htmx_views:select", args=(self.lookup_channel,)),
                "hx-trigger": f"change from:#id_{self.parent_name}",
                "hx-include": f"#id_{self.parent_name}",
            }
        )
        kargs["attrs"] = attrs

        super().__init__(*args, **kargs)

    def get_context(self, name, value, attrs):
        """Customise the context."""
        attrs = attrs or {}
        attrs.update(
            {
                "hx-target": f"#id_{name}",
            }
        )
        ret = super().get_context(name, value, attrs)
        return ret
