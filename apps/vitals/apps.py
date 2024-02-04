# Django imports
from django.apps import AppConfig


class VitalsConfig(AppConfig):

    """Config class for VITALS."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "vitals"

    def ready(self):
        """Import the singal handler when we're good to start."""
        # app imports
        from . import signals
