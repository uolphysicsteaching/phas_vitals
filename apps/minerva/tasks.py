# -*- coding: utf-8 -*-
"""Celery taks for the minerva app."""
# Python imports
import logging
from datetime import datetime

# external imports
from celery import shared_task
from constance import config
from minerva.models import Module, Test_Score
from pytz import UTC

# app imports
from phas_vitals.celery import PHASTask

logger = logging.getLogger(__name__)


@shared_task
def import_gradebook():
    """Import a spreadsheet of the full Minerva gradebook download."""
    # Really do stuff
    for module in Module.objects.all():
        if module.update_from_json() is None:
            logger.info(f"Failed import for {module.name}")

    config.LAST_MINERVA_UPDATE = datetime.now(tz=UTC)


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_vitals(requests):
    """For each vital that uses this test, check whether a vital is passed and update as necessary."""
    ids = list(set([request.args[0] for request in requests]))  # Pass through set deduplicates account.pk values
    test_scores = Test_Score.objects.get(pk__in=ids)
    for test_score in test_scores:
        for vm in test_score.test.vitals_mappings.all().prefetch_related(
            "vital"
        ):  # For each vital that this test could pass
            vm.vital.check_vital(test_score.user)
