"""Utility Admin Operations."""

# Python imports
import contextlib
from collections.abc import Iterable

# Django imports
from django.apps import apps
from django.contrib import admin
from django.db.models import Model

# Register your models here.


@contextlib.contextmanager
def get_admin(model):
    """Context Manager to edit the admin class for a given model.

    Args:
        model (Model or str):
            Model class to get admin for. If a string, then should be "app.model_name"

    Yields:
        (ModelAdmin):
            Model Admin class.

    Notes:
        After looking up the ModelAdmin class directly from django.contrib.admin.site._registry,
        the ModelAdmin is unregistered from the admin site and returned to the user to adjust. On exit,
        the context manager re-registers the class, thus allowing the class definition to be modified outside
        of the app that created it.

        The lookup of the model by app_label.model_name currently does do an import, so it might still be possible
        to get circular definitions going on.
    """
    if isinstance(model, str):  # Load the correct model
        app_label, model_name = model.split(".")
        model = apps.get_model(app_label, model_name, require_ready=True)
    if not (isinstance(model, type) and issubclass(model, Model)):
        raise TypeError(f"{model} should be a subclass of django.db.models.Model not a {type(model)}")
    if model not in admin.site._registry:
        raise ValueError(f"{model} doesn't have a registered admin yet!")
    ret = admin.site._registry[model].__class__
    admin.site.unregister(model)
    yield ret
    admin.register(model)(ret)


def add_inlines(model, inline, related_name):
    """Patch the model Admin to add the inlines."""
    with get_admin(model) as model_admin:
        model_admin.inlines += (inline,)
        model_admin.fieldsets[0][1]["classes"].append(f"baton-tab-inline-{related_name}")


def add_action(model, action_func):
    """Patch the model admin to add the action."""
    with get_admin(model) as model_admin:
        model_admin.actions += (action_func,)


def patch_admin(model, **kargs):
    """Monkeypatch the admin site of the given model.

    Args:
        model (Model or str):
            Model class to patch the admin site for.

    Keyword Arguments:
        (str : Atrtib)-> Any: value:
            The ModelAdmin Attribute and new Value pairs.

    If the ModelAdmin already has the attribute and it's a collection, then this will try to append,
    update or extend the attribute value with the new one. Otherwise, the attribute value is just replaced.
    """
    with get_admin(model) as model_admin:
        for attr, value in kargs.items():
            old_value = getattr(model_admin, attr, None)
            if isinstance(old_value, dict):
                old_value |= value
            elif isinstance(old_value, tuple):
                new_value = list(old_value)
                if isinstance(value, Iterable):
                    new_value.extend(value)
                else:
                    new_value.append(value)
                setattr(model_admin, attr, tuple(new_value))
            elif isinstance(old_value, list):
                if isinstance(value, Iterable):
                    old_value.extend(value)
                else:
                    old_value.append(value)
            else:
                setattr(model_admin, attr, value)


# external imports
from sitetree.admin import TreeItemAdmin as model_admin

model_admin.fieldsets[0][1]["classes"] = (
    "baton-tabs-init",
    "baton-tab-fs-basic",
    "baton-tab-fs-access",
    "baton-tab-fs-display",
    "baton-tab-fs-extra",
)
model_admin.fieldsets[1][1]["classes"] = ("tab-fs-access",)
model_admin.fieldsets[2][1]["classes"] = ("tab-fs-display",)
model_admin.fieldsets[3][1]["classes"] = ("tab-fs-extra",)
