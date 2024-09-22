# -*- coding: utf-8 -*-
"""Celery taks for the util app."""
# Python imports
import logging
from datetime import timedelta

# Django imports
from django.utils import timezone as tz

# external imports
from celery import shared_task
from constance import config
from django_celery_results.models import TaskResult

logger = logging.getLogger("celery_tasks")


@shared_task
def cleanup_task_results():
    """Task that drops TaskResults that are older than a defined period."""
    past = tz.now() - timedelta(days=config.TASK_CLEANUP)
    to_drop = TaskResult.objects.exclude(date_done__gt=past)
    logger.info("Dropping {to_drop.count()} Task Result objects older than {config.TASK_CLEANUP} days.")
    return to_drop.delete()


@shared_task
def heartbeat():
    """Null task to check celery beat is running."""
    config.HEARTBEAT = tz.now()
    return config.HEARTBEAT
