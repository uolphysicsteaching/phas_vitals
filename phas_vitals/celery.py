# -*- coding: utf-8 -*-
"""Configure celery for phas_vitals."""
# Python imports
import functools
import os

# Django imports
from django.db import transaction

# external imports
from celery import Celery
from celery.canvas import Signature
from celery.contrib.django.task import DjangoTask
from celery_batches import Batches

__all__ = ["tasks"]

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "phas_vitals.settings.production")
tasks = Celery("phas_vitals")

# Import settings from main settings where they are prefixed with CELERY
tasks.config_from_object("django.conf:settings", namespace="CELERY")


# Load task modules from all registered Django apps.
tasks.autodiscover_tasks()


class PHASTask(Batches, DjangoTask):

    """Provides a mixin Class for tasks that can be batched and just delay_on_commit."""


def delay_on_commit(self, *args, **kwargs) -> None:
    """Call :meth:`~celery.app.task.Task.delay` with Django's ``on_commit()``."""
    transaction.on_commit(functools.partial(self.delay, *args, **kwargs))


def apply_async_on_commit(self, *args, **kwargs) -> None:
    """Call :meth:`~celery.app.task.Task.apply_async` with Django's ``on_commit()``."""
    transaction.on_commit(functools.partial(self.apply_async, *args, **kwargs))


setattr(Signature, "delay_on_commit", delay_on_commit)
setattr(Signature, "apply_async_on_commit", apply_async_on_commit)


@tasks.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task that prints things."""
    print(f"Request: {self.request!r}")
