"""Models for util app."""
# Django imports
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db import models

# external imports
import numpy as np
from matplotlib.cm import RdYlGn as color
from sitetree.models import TreeBase, TreeItemBase


def patch_model(model, name=None, prep=None):
    """Decorator to monkey-patch a function into a model.

    Args:
        model (model):
            Django model to monkey -patch method into.

    Keyword Arguments:
        name (str,None):
            Name of method on the model (default None is to use the function's name)
        prep (callable):
            Callable to use to prepare the function with before adding it to the model (default None is to do nothing).

    Returns:
        Actual decorator
    """
    if isinstance(model, str):
        if "." in model:
            app_label, model = model.split(".")
        else:
            app_label = ContentType.objects.get(model=model).app_label
        model = apps.get_model(app_label, model)
    if not issubclass(model, models.Model):
        raise ImproperlyConfigured(f"model argument to patch should either be a string or model - not a {type(model)}")

    def patch_model_decorator(func):
        if name is None:
            attr_name = func.__name__
        else:
            attr_name = name
        if prep is not None:
            doc = func.__doc__
            func = prep(func)
            func.__doc__ = doc
        setattr(model, attr_name, func)

    return patch_model_decorator


def colour(value: float, contrast: bool = False) -> str:
    """Turn a float value into a colour scheme."""
    if not isinstance(value, float) or np.isnan(value):
        return "#ffffff"
    value = value / 120
    rgb = (np.array(color(value)) * 255).astype(int)[:3]
    if contrast:
        return "#000000" if rgb.mean() > 96 else "#ffffff"
    return "#" + "".join([f"{x:02X}" for x in rgb])


def contrast(colour: str) -> str:
    """Take a Hex string and convert to a contrasting colour string."""
    if len(colour) < 7:
        return "#000000"
    if colour[0] == "#":
        colour = colour[1:]
    elif colour[:2] == "0x":
        colour = colour[2:]
    try:
        col: int = int(colour, 16)
        high = col // (256 * 256)
        col -= high * 256**2
        med = col // 256
        low = col - med * 256
        avg = (high + med + low) / 3
    except (ValueError, TypeError):
        avg = 0
    return "#000000" if avg > 128 else "#ffffff"


# Create your models here.


class GroupedTree(TreeBase):
    """Just a placeholder."""


class GroupedTreeItem(TreeItemBase):
    """Add many to many field for reference to groups to control access."""

    TRISTATE = [(0, "--"), (1, "Grant"), (2, "Block")]

    groups = models.ManyToManyField(
        "auth.Group", related_name="allowed_menu_items", verbose_name="Access Groups", blank=True
    )
    not_groups = models.ManyToManyField(
        "auth.Group", related_name="blocked_menu_items", verbose_name="Blocked Groups", blank=True
    )
    access_staff = models.IntegerField(default=0, choices=TRISTATE, verbose_name="Staff Access")
    access_superuser = models.IntegerField(default=0, choices=TRISTATE, verbose_name="Superuser Access")

    def access_check(self, tree):
        """Check whether access is ok."""
        auth = tree.check_access_auth(self, tree.context)
        user = tree.current_request.user

        if auth and user.is_authenticated:  # Now check groups
            # If access_staff is 1 or 2, check whether user is or ir not staff. Necessary but not sufficient
            if (self.access_staff == 2 and user.is_staff) or (self.access_staff == 1 and not user.is_staff):
                return False

            # If access_superuser is 1 or 2, checker whether user is or is not superuser. Necessary but not sufficient
            if (self.access_superuser == 2 and user.is_superuser) or (
                self.access_superuser == 1 and not user.is_superuser
            ):
                return False

            user_groups = set([x[0] for x in user.groups.all().values_list("name")])
            if self.groups.all().count() > 0:  # If no groups defined, then don't test
                item_groups = set([x[0] for x in self.groups.all().values_list("name")])
                if len(item_groups & user_groups) == 0:  # User not in allowed groups - block
                    return False
            if self.not_groups.all().count() > 0:  # If no groups defined, then don't test
                item_groups = set([x[0] for x in self.not_groups.all().values_list("name")])
                if len(item_groups & user_groups) > 0:  # User in at least 1 blocked group - block
                    return False

        return None  # If we can't make a decision based on groups, don't take a decision at all.
