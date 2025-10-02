# -*- coding: utf-8 -*-
"""Celery tasks for the accounts app."""
# Python imports
import logging
from pathlib import Path

# Django imports
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import transaction
from django.db.models import Count, Q

# external imports
import numpy as np
import pandas as pd
from celery import shared_task
from constance import config
from django_auth_adfs.config import provider_config

# app imports
from phas_vitals import celery_app
from phas_vitals.tasks import PHASTask

# app imports
from .models import Account

logger = logging.getLogger("celery_tasks")


@celery_app.task
def update_all_users():
    """Update all users marked as needing records updated.

    Find all users with Account.update_vitals==True and:
        1. For each passed test, check that the associated VITALs are marked passed.
        2. recalculate the scores for that user.
        3. save the user record.
    """
    logger.debug("Running update all users task")
    TestCategory = apps.get_model("minerva", "testcategory")
    SummaryScore = apps.get_model("minerva", "summaryscore")
    ModuleEnrollment = apps.get_model("minerva", "moduleenrollment")
    accounts = (
        Account.objects.prefetch_related("module_enrollments", "summary_scores", "VITALS")
        .annotate(cnt=Count("modules"))
        .filter(cnt__gt=0)
    )
    VITAL = apps.get_model("vitals", "vital")

    summaries = SummaryScore.objects.filter(student__in=accounts)
    valid_categories = TestCategory.objects.filter(Q(in_dashboard=True) | Q(dashboard_plot=True))
    drop_summaries = summaries.exclude(category__in=valid_categories).distinct().delete()

    for account in accounts.all():
        vital_list = VITAL.objects.filter(module__in=account.modules.all())
        logger.debug(f"Updating for {account=} total of {vital_list.count()=} VITALs")
        for vital in vital_list:
            if vital.check_vital(account):
                logger.debug(f"{account} updated")
        # Drop summaries that relate to modules we're not enrolled in now.
        account.summary_scores.exclude(module__in=account.modules.all()).delete()
        summaries = account.summary_scores.filter(module__in=account.modules.all())
        valid_summary_pk = [x[0] for x in summaries.values_list("category")]
        for cat in (
            valid_categories.filter(module__in=account.modules.all()).exclude(pk__in=valid_summary_pk).distinct()
        ):  # Only the categories for modules account is enrolled in, minus ones where a summary already exists.
            summary, _ = SummaryScore.objects.get_or_create(
                enrollment=account.module_enrollments.get(module=cat.module), category=cat
            )
        summaries = account.summary_scores.filter(module__in=account.modules.all())
        for summary in summaries:
            summary.calculate()
        summaries.bulk_update(summaries, ["score", "data"])
        try:
            summary = np.array(summaries.values_list("module__credits", "category__weighting", "score")).astype(float)
            if summary.size == 0:  # No results must be a zero score
                account.activity_score = np.nan
            else:
                summary = summary[~np.any(np.isnan(summary), axis=1)]  # remove NaNs
                account.activity_score = float(
                    np.nansum(np.nanprod(summary, axis=1)) / np.nansum(np.nanprod(summary[:, :2], axis=1))
                )
        except (ValueError, ZeroDivisionError):
            account.activity_score = np.nan
        logger.debug(f"Setting account {account} activity_score {account.activity_score}")
        account.save()


@shared_task()
def update_user_from_graph(user_pk, obo_access_token):
    """Use MSGraph API to update a user account."""
    # At the moment I don't have outgoing msgraph.com I think
    url = "https://graph.microsoft.com/v1.0/me?$select=employeeId,givenName,surname"
    logger.debug(f"Starting MS Graph call for {user_pk}")

    headers = {"Authorization": "Bearer {}".format(obo_access_token)}
    response = provider_config.session.get(url, headers=headers, timeout=30, verify=False)
    logger.debug(f"Got a {response.status_code} - {response.json()}")

    if response.status_code in [400, 401]:
        logger.error(f"MS Graph server returned an error: {response.json()['message']}")
        raise PermissionDenied

    if response.status_code != 200:
        logger.error("Unexpected MS Graph response: {response.content.decode()}")
        raise PermissionDenied

    payload = response.json()

    with transaction.atomic():  # We're in a potential race condition here so use db transactions
        try:
            user = Account.objects.get(pk=user_pk)
        except ObjectDoesNotExist:
            logger.debug("No such user {user_pk} giving up.")
            return

        user.number = int(payload["employeeId"])
        user.last_name = payload["surname"]
        user.givenName = payload["givenName"]
        user.save()


@celery_app.task
def find_unjustified_vitals():
    """Check all accounts for unexpected VITALs and note in a spreadsheet."""
    missing = []
    for account in Account.objects.all():
        logger.debug(f"Checking VITAL results match tests {account.display_name}")
        drop = []
        for vital_r in account.vital_results.all():
            possible_tests = vital_r.vital.tests.all()
            test_attempts = account.test_results.filter(test__in=possible_tests.all())
            if (
                possible_tests.count() > 0
                and test_attempts.count() > 0
                and test_attempts.filter(passed=True).count() > 0
            ):  # passed at least one qualifying test
                continue
            logger.debug(f"Issues with VITAL {vital_r.vital} for {account.display_name}")
            missing.append(
                {
                    "Student": account.display_name,
                    "VITAL": vital_r.vital,
                    "Possible Tests": "\n".join([x.name for x in possible_tests.all()]),
                    "Attempts": "\n".join([str(x) for x in test_attempts.all()]),
                }
            )
            if test_attempts.count() == 0:  # Can drop this Vital Result as untested.
                drop.append(vital_r.pk)
    logger.debug(f"Toal of {len(missing)} unexpected VITAL passes.")
    if drop:
        VITAL_Result = apps.get_model("vitals", "vital_result")
        VITAL_Result.objects.filter(pk__in=drop).delete()
    if not missing:
        return
    datapath = Path(settings.MEDIA_ROOT) / "data" / "Excess_VITALS.xlsx"
    if not datapath.exists():
        df = pd.DataFrame(missing)
        df.to_excel(datapath)
    else:
        df = pd.from_excel(datapath)
        df = pd.concat([df, pd.DataFrame(missing)])
        df.to_excel(datapath)
