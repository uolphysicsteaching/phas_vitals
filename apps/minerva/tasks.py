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
from phas_vitals import celery_app
from phas_vitals.celery import PHASTask

logger = logging.getLogger("celery_tasks")

update_all_users = celery_app.signature("accounts.tasks.update_all_users")


@shared_task
def import_gradebook():
    """Import a spreadsheet of the full Minerva gradebook download."""
    logger.debug("Running gradebook import")
    # Really do stuff
    imported_modules = []
    for module in Module.objects.all():
        logger.debug(f"Attempting to import {module.key}")
        if module.update_from_json() is None:
            logger.info(f"Failed import for {module.name}")
        else:
            imported_modules.append(module.key)
            config.LAST_MINERVA_UPDATE = module.json_updated
            logger.debug(f"Imported {module.key} {module.json_updated}")

    logger.debug("Updated constance.config")
    update_all_users.delay()
    return imported_modules


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_vitals(requests):
    """For each vital that uses this test, check whether a vital is passed and update as necessary."""
    ids = list(set([request.args[0] for request in requests]))  # Pass through set deduplicates account.pk values
    logger.debug(f"Running minerva.update_vitals for {ids}")
    test_scores = Test_Score.objects.filter(pk__in=ids)
    for test_score in test_scores:
        logger.debug(f"Looking at test score {test_score}")
        for vm in test_score.test.vitals_mappings.all().prefetch_related(
            "vital"
        ):  # For each vital that this test could pass
            logger.debug(f"Checking mapping {vm}")
            vm.vital.check_vital(test_score.user)
