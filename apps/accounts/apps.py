# Python imports
from os.path import basename, dirname

# Django imports
from django.apps import AppConfig
from django.db.utils import ProgrammingError


class AccountsConfig(AppConfig):
    """Django App config object for the accounts app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = basename(dirname(__file__))

    def ready(self):
        """When app is up and running, import api."""
        try:
            # Django imports
            from django.contrib.auth.models import Permission
            from django.contrib.contenttypes.models import ContentType

            # app imports
            from . import api  # pylint: disable=unused-import
            from .models import Account

            content_type = ContentType.objects.get_for_model(Account)
            Permission.objects.get_or_create(
                codename="is_tutor",
                name="Can Update Tutorial Attendance",
                content_type=content_type,
            )
            Permission.objects.get_or_create(
                codename="is_superuser",
                name="Can Review Whole Cohort",
                content_type=content_type,
            )
        except (ImportError, ProgrammingError):
            pass
