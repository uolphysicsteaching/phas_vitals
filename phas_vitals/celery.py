# -*- coding: utf-8 -*-
"""Configure celery for phas_vitals."""
# Python imports
import os

# external imports
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "phas_vitals.settings.production")
app = Celery("phas_vitals")

# Import settings from main settings where they are prefixed with CELERY
app.config_from_object("django.conf:settings", namespace="CELERY")


# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task that prints things."""
    print(f"Request: {self.request!r}")
