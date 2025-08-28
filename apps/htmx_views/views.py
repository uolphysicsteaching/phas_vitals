# -*- coding: utf-8 -*-
"""View support classes and functions for htmx-views."""

# Python imports
import logging
import re
from contextlib import contextmanager

# Django imports
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.views import View
from django.views.generic import TemplateView

# external imports
from ajax_select import registry

logger = logging.getLogger(__name__)


@contextmanager
def temp_attr(obj, attr, value):
    """Temporarily set the value of an attribute and restore it afterwards."""
    # Check if the attribute originally exists on the object
    has_attr = hasattr(obj, attr)
    original_value = getattr(obj, attr, None)

    # Set the attribute to the new value
    setattr(obj, attr, value)

    try:
        # Yield control back to the caller
        yield
    finally:
        if has_attr:
            # Restore the original value if the attribute existed
            setattr(obj, attr, original_value)
        else:
            # Delete the attribute if it didn't exist originally
            delattr(obj, attr)


def dispatch(self, request, *args, **kwargs):
    """Dispatch method that becomes htmx aware.

    If the =`htmx` request attribute is set (by django-htmx) and the method name is in either
    `self.http_method_names` or `self.htmx_method_names` then try to locate the method
    `htmx_<http_verb>` method and call that or else fall back to the regular `<http_verb>` method.

    If an approrpiate method can't be located, call `self.http_method_bot_allowed` for error handline.

    If the `htmx` request attrobute is not set or is False, then fall back to the original dispatch.
    """
    if not getattr(request, "htmx", False):  # Not an HTMX aware request
        return self._non_htmx_dispatch(request, *args, **kwargs)

    # Allow different  allowed methods for htmx
    allowed_names = getattr(self, "htmx_http_method_names", self.http_method_names)

    if request.method.lower() in allowed_names:
        handler = getattr(
            self, f"htmx_{request.method.lower()}", getattr(self, request.method.lower(), self.http_method_not_allowed)
        )
    else:
        handler = self.http_method_not_allowed
    return handler(request, *args, **kwargs)


class HTMXProcessMixin:
    """Provide versions of the htmx_`<http_verb>` methods that will delegate to trigger specific methods.

    Each http verb DELETE,GET,PATCH,POST,PUT's htmx_<verb> method will look at the request.htmx attriobute
    to see if htmx_<verb>_<trigger_name>, htmx_<verb>_<trigger>, htmx_<verb>_<target> is a method and then pass
    on to the first matching method. If no match is foumd, the `http_method_not_allowed` method is used instead.
    """

    def __init__(self, *args, **kwargs):
        """Setup the _htmc_call attribute for later use."""
        super().__init__(*args, **kwargs)
        self._htmx_get_context_data = False
        self._htmx_get_context_object_name = False
        self._htmx_get_template_names = False

    def htmx_elements(self):
        """Iterate over possible htmx element sources."""
        for attr in ["trigger_name", "trigger", "target"]:
            if elem := getattr(self.request.htmx, attr, None):
                elem = re.sub(r"[^A-Za-z0-9_]", "", elem).lower()
                if settings.DEBUG:
                    logger.debug(elem)
                yield elem

    def get_context_data(self, **kwargs):
        """Get context data being aware of htmx views."""
        if not getattr(self.request, "htmx", False) or self._htmx_get_context_data:  # Default behaviour
            return super().get_context_data(**kwargs)

        # Look for a request specific to the element involved.
        for elem in self.htmx_elements():
            handler = getattr(self, f"get_context_data_{elem}", False)
            if handler:
                with temp_attr(self, "_htmx_get_context_data", True):
                    return handler(**kwargs)
        return super().get_context_data(**kwargs)

    def get_context_object_name(self, object_list):
        """Get context object name being aware of htmx elements.

        If the get_context_name_<element> method needs to call usper, it should set a keyword
        argument, _default to be True to avoid a recursive loop.
        """
        if not getattr(self.request, "htmx", False) or self._htmx_get_context_object_name:  # Default behaviour
            return super().get_context_object_name(object_list)

        # Look for a request specific to the element involved.
        for elem in self.htmx_elements():
            if handler := getattr(self, f"get_context_object_name{elem}", False):
                with temp_attr(self, "_htmx_get_context_object_name", True):
                    return handler(object_list)
            if sub_name := getattr(self, f"context_object_{elem}", False):
                return sub_name

        logger.debug("Super")

        return super().get_context_object_name(object_list)

    def get_template_names(self):
        """Look for htmx specific templates."""
        if not getattr(self.request, "htmx", False) or self._htmx_get_template_names:  # Default behaviour
            return super().get_template_names()

        # Look for a request specific to the element involved.
        for elem in self.htmx_elements():
            handler = getattr(self, f"get_template_names_{elem}", False)
            if handler:
                if settings.DEBUG:
                    logger.debug(f"Template_handler: {handler.__name__}")
                with temp_attr(self, "_htmx_get_template_names", True):
                    return handler()
            sub_name = getattr(self, f"template_name_{elem}", False)
            if sub_name:
                if settings.DEBUG:
                    logger.debug(f"Template_name: {sub_name}")
                return sub_name
        return super().get_template_names()

    def htmx_delete(self, request, *args, **kwargs):
        """Delegate HTMX DELETE requests.

        Looks for the element that is related to the request by inspecting the `request.htmx` `trigger_name`, trigger
        and target attributes in turn. If no matching `htmx_delete_<name>` methods are found, return the
        `method_not_allowed` result instrad.
        """
        for elem in self.htmx_elements():
            handler = getattr(self, f"htmx_delete_{elem}", False)
            if handler:
                break
        else:
            handler = getattr(self, "delete", self.http_method_not_allowed)
        if settings.DEBUG:
            logger.debug(f"HTMX Method handler: {handler.__name__}")
        return handler(request, *args, **kwargs)

    def htmx_get(self, request, *args, **kwargs):
        """Delegate HTMX GET requests.

        Looks for the element that is related to the request by inspecting the `request.htmx` `trigger_name`, trigger
        and target attributes in turn. If no matching `htmx_get_<name>` methods are found, return the
        `method_not_allowed` result instrad.
        """
        for elem in self.htmx_elements():
            handler = getattr(self, f"htmx_get_{elem}", False)
            if handler:
                break
        else:
            handler = getattr(self, "get", self.http_method_not_allowed)
        if settings.DEBUG:
            logger.debug(f"HTMX Method handler: {handler.__name__}")
        return handler(request, *args, **kwargs)

    def htmx_patch(self, request, *args, **kwargs):
        """Delegate HTMX PATCH requests.

        Looks for the element that is related to the request by inspecting the `request.htmx` `trigger_name`, trigger
        and target attributes in turn. If no matching `htmx_patch_<name>` methods are found, return the
        `method_not_allowed` result instrad.
        """
        for elem in self.htmx_elements():
            handler = getattr(self, f"htmx_patch_{elem}", False)
            if handler:
                break
        else:
            handler = getattr(self, "patch", self.http_method_not_allowed)
        if settings.DEBUG:
            logger.debug(f"HTMX Method handler: {handler.__name__}")
        return handler(request, *args, **kwargs)

    def htmx_post(self, request, *args, **kwargs):
        """Delegate HTMX POST requests.

        Looks for the element that is related to the request by inspecting the `request.htmx` `trigger_name`, trigger
        and target attributes in turn. If no matching `htmx_post_<name>` methods are found, return the
        `method_not_allowed` result instrad.
        """
        for elem in self.htmx_elements():
            handler = getattr(self, f"htmx_post_{elem}", False)
            if handler:
                break
        else:
            handler = getattr(self, "post", self.http_method_not_allowed)
        if settings.DEBUG:
            logger.debug(f"HTMX Method handler: {handler.__name__}")
        return handler(request, *args, **kwargs)

    def htmx_put(self, request, *args, **kwargs):
        """Delegate HTMX PUT requests.

        Looks for the element that is related to the request by inspecting the `request.htmx` `trigger_name`, trigger
        and target attributes in turn. If no matching `htmx_put_<name>` methods are found, return the
        `method_not_allowed` result instrad.
        """
        for elem in self.htmx_elements():
            handler = getattr(self, f"htmx_put_{elem}", False)
            if handler:
                break
        else:
            handler = getattr(self, "put", self.http_method_not_allowed)
        if settings.DEBUG:
            logger.debug(f"HTMX Method handler: {handler.__name__}")
        return handler(request, *args, **kwargs)


class HTMXFormMixin(HTMXProcessMixin):
    """Provide additional methods to adapt FormView and friends for htmx requests as well."""

    def __init__(self, *args, **kwargs):
        """Setup the _htmc_call attribute for later use."""
        super().__init__(*args, **kwargs)
        self._htmx_form_valid = False
        self._htmx_form_invalid = False

    def form_valid(self, form):
        """Look for HTMX form valid handlers.

        If request.htmx is not set, then return the parent class form_valid, otherwise look for an element
        specific htmx_form_valid_<name> method, or failing that just an htmx_form_valid meothd. Fnally,
        give up and return the parent form_valid.

        Notes:
            htmx_form_valid* methods must not call super().form_valid - otherwise an infinite recursion happens!
        """
        if not getattr(self.request, "htmx", False) or self._htmx_form_valid:  # Non HTMX requests
            return super().form_valid(form)
        for elem in self.htmx_elements():
            if settings.DEBUG:
                logger.debug(f"Looking for htmx_form_valid_{elem}")
            handler = getattr(self, f"htmx_form_valid_{elem}", False)
            if handler:
                with temp_attr(self, "_htmx_form_valid", True):
                    return handler(form)
        if handler := getattr(self, "htmx_form_valid", False):
            with temp_attr(self, "_htmx_form_valid", True):
                return handler(form)
        return super().form_valid(form)

    def form_invalid(self, form):
        """Look for HTMX form valid handlers.

        If request.htmx is not set, then return the parent class form_invalid, otherwise look for an element
        specific htmx_form_invalid_<name> method, or failing that just an htmx_form_invalid meothd. Fnally,
        give up and return the parent form_invalid.

        Notes:
            htmx_inform_valid* methods must not call super().form_valid - otherwise an infinite recursion happens!
        """
        if not getattr(self.request, "htmx", False) or self._htmx_form_invalid:  # Non HTMX requests
            return super().form_invalid(form)

        for elem in self.htmx_elements():
            handler = getattr(self, f"htmx_form_invalid_{elem}", False)
            if settings.DEBUG:
                logger.debug(f"Looking for htmx_form_invalid_{elem}")
            if handler:
                with temp_attr(self, "_htmx_form_invalid", True):
                    return handler(form)
        if handler := getattr(self, "htmx_form_invalid", False):
            with temp_attr(self, "_htmx_form_invalid", True):
                return handler(form)
        return super().form_invalid(form)


class _LocalUserPassesTest:
    """Implement the bits of UserPassesTestMixin that we need wiuthout triggering the early import."""

    def dispatch(self, request, *args, **kwargs):
        user_test_result = self.test_func()
        if not user_test_result:
            # Django imports
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(self.request.get_full_path(), self.login_url(), self.redirect_field_name())
        return super().dispatch(request, *args, **kwargs)


class LinkedSelectEndpointView(_LocalUserPassesTest, TemplateView):
    """Endpoint for htmx_views:select urls for linked select widget."""

    template_name = "htmx_views/widgets/options.html"
    login_url = settings.LOGIN_URL
    redirect_field_name = "next"

    def test_func(self):
        """Get our lookup and use authentication if required."""
        try:
            self.lookup_channel = self.kwargs.get("lookup_channel")
            self.parent = self.kwargs.get("parent", None)
            self.lookup = registry.get(self.kwargs.get("lookup_channel"))
        except ImproperlyConfigured:
            return False
        if hasattr(self.lookup, "check_auth"):
            try:
                self.lookup.check_auth(self.request)
            except PermissionDenied:
                return False
        return True

    def get_context_data(self, **kwargs):
        """Add the option_list to the context."""
        if self.parent is None:
            self.parent = getattr(self.lookup, "parameter_name", None)
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
        opts = {"---------": None}
        if query:
            opts.update({str(x): x.pk for x in self.lookup.get_query(query, self.request).distinct()})
        context["options"] = opts
        return context


if not hasattr(View, "_bon_htmx_dispatch"):  # View needs monkey patching
    setattr(View, "_non_htmx_dispatch", View.dispatch)
    setattr(View, "dispatch", dispatch)
