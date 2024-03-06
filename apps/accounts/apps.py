# Python imports
from os.path import basename, dirname

# Django imports
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Django App config object for the accounts app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = basename(dirname(__file__))

    def ready(self):
        """When app is up and running, import api."""
        try:
            # app imports
            from . import api  # pylint: disable=unused-import
        except ImportError:
            pass
