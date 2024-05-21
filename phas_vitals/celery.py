# -*- coding: utf-8 -*-
"""Configure celery for phas_vitals."""
# Python imports
import os

# external imports
from celery import Celery

__all__ = ["tasks"]

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "phas_vitals.settings.production")
tasks = Celery("phas_vitals")

# Import settings from main settings where they are prefixed with CELERY
tasks.config_from_object("django.conf:settings", namespace="CELERY")


# Load task modules from all registered Django apps.
tasks.autodiscover_tasks()


@tasks.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task that prints things."""
    print(f"Request: {self.request!r}")
