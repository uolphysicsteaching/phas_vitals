# Django imports
from django.apps import AppConfig


class MinervaConfig(AppConfig):
    """Django app config object for minerva interface app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "minerva"

    def ready(self):
        """When app is up and running, import api."""
        try:
            # app imports
            from . import api  # pylint: disable=unused-import
        except ImportError:
            pass
