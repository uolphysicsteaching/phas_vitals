# Django imports
from django.apps import AppConfig


class VitalsConfig(AppConfig):
    """Config class for VITALS."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "vitals"

    def ready(self):
        """Import the signal handler when we're good to start."""
        # app imports
        try:
            # app imports
            from . import api  # pylint: disable=unused-import
            from . import signals  # pylint: disable=unused-import
        except ImportError:
            pass
