# -*- coding: utf-8 -*-
"""Celery taks for the minerva app."""
# Python imports
from datetime import datetime

# Django imports
from django.core.exceptions import ObjectDoesNotExist

# external imports
from celery import shared_task
from constance import config
from minerva.models import Test_Score
from pytz import UTC


@shared_task
def import_gradebook():
    """Import a spreadsheet of the full Minerva gradebook download."""
    # Really do stuff
    config.LAST_MINERVA_UPDATE = datetime.now(tz=UTC)


@shared_task
def update_vitals(test_score_pk):
    """For each vital that uses this test, check whether a vital is passed and update as necessary."""
    try:
        test_score = Test_Score.objects.get(pk=test_score_pk)
    except ObjectDoesNotExist:
        return  # don't worry if the test_Scire went before we got there!
    for vm in test_score.test.vitals_mappings.all().prefetch_related(
        "vital"
    ):  # For each vital that this test could pass
        vm.vital.check_vital(test.user)
