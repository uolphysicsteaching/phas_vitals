"""Helpers for optional HTMX views integrations."""

# Python imports
from importlib import import_module


def get_ajax_select_registry():
    """Return the ajax-select registry or explain how to enable linked selects."""
    try:
        ajax_select = import_module("ajax_select")
    except ModuleNotFoundError as error:
        if error.name != "ajax_select":
            raise
        raise ImportError(
            "Linked-select support requires the optional dependency "
            "'django-ajax-selects'. Install it before importing "
            "'htmx_views.widgets' or 'htmx_views.urls'."
        ) from error
    return ajax_select.registry
