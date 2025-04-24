from __future__ import unicode_literals

# Django imports
from django.apps import AppConfig


class ProjectConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tutorial"

    def ready(self):
        """When app is up and running, import api."""
        try:
            # app imports
            from . import api  # pylint: disable=unused-import
        except ImportError:
            pass
