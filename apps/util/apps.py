# Django imports
"""Application config settings for util app."""
# Django imports
from django.apps import AppConfig


class UtilConfig(AppConfig):
    """Util config object."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "util"

    def ready(self):
        """Hook when application is ready."""
        # app imports
        from . import tree  # pylint: disable=unused-import
