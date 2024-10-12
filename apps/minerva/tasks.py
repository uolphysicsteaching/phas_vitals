# -*- coding: utf-8 -*-
"""Celery taks for the minerva app."""
# Python imports
import logging
from datetime import datetime
from pathlib import Path

# Django imports
from django.conf import settings

# external imports
import pandas as pd
from celery import shared_task
from constance import config
from djano.utils import timezone as tz
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


@shared_task()
def take_time_series(module_code="PHAS1000"):
    """Load DataFrames and add new row for the current date."""
    datapath = Path(settings.MEDIA_ROOT) / "data"
    attrs = ["activity_score", "tests_score", "labs_score", "coding_score", "vitals_score", "engagement"]
    try:
        module = Module.objects.get(code=module_code)
    except ObjectDoesNotExist:
        logger.debug("Failed to run time series collection for module {module_code}")
    data = module.students.all()
    for attr in attrs:
        filename = "data_{attr}.xlsx"
        if (filepath := (datapath / "filename")).exists():
            df = pd.read_excel(filepath).set_index("Date")
        else:
            df = pd.DataFrame(columns=["Date"]).set_index("Date")
        row = {entrynumber: getattr(entry, attr, np.nan) for entry in data}
        date = tz.now().date()
        if date in df.index:  # Check for double running on the same day!
            for k, v in row.items():
                df.loc[date, k] = v
        else:
            row["Date"] = date
            row_df = pd.DataFrame([row]).set_index("Date")
            df = pd.concat((df, row))
        df.to_excel(filepath)
