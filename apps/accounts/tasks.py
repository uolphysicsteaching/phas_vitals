# -*- coding: utf-8 -*-
"""Celery tasks for the accounts app."""
# Python imports
import logging
from pathlib import Path

# Django imports
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import transaction

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


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_tests_score(requests):
    """Run the update on the account after a new test score has been set.

    Args:
        account (pk): primary key for account to update
        chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts

    try:
        accounts = Account.objects.filter(pk__in=list(data.keys()))
        for account in accounts:
            logger.debug(f"Updating tests for {account.username}")
            try:
                account.tests_score = np.round(
                    100.0
                    * account.passed_tests.count()
                    / (account.passed_tests.count() + account.failed_tests.count() + account.untested_tests.count())
                )
            except (ValueError, ZeroDivisionError):
                account.tests_score = None
        Account.objects.bulk_update(accounts, ["tests_score"])
        # Now chain the next method since we've done the null update
        for account in accounts:
            if data[account.pk]:
                update_labs_score.delay(account.pk, True)
    except Exception as err:
        logger.debug(f"Exception in update_tests_score: {err}")


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_labs_score(requests):
    """Run the update on the account after a new test score has been set.

    Args:
        account (pk): primary key for account to update
        chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts
    try:
        accounts = Account.objects.filter(pk__in=list(data.keys()))
        for account in accounts:
            logger.debug(f"Updating Labs for {account.username}")
            try:
                account.labs_score = np.round(
                    100.0
                    * account.passed_labs.count()
                    / (account.passed_labs.count() + account.failed_labs.count() + account.untested_labs.count())
                )
            except (ValueError, ZeroDivisionError):
                account.labs_score = None
        Account.objects.bulk_update(accounts, ["labs_score"])
        # Now chain the next method since we've done the null update
        for account in accounts:
            if data[account.pk]:
                update_coding_score.delay(account.pk, True)
    except Exception as err:
        logger.debug(f"Exception in update_all_labs: {err}")


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_coding_score(requests):
    """Run the update on the account after a new test score has been set.

    Args:
        account (pk): primary key for account to update
        chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts
    try:
        accounts = Account.objects.filter(pk__in=list(data.keys()))
        for account in accounts:
            logger.debug(f"Updating Labs for {account.username}")
            try:
                account.coding_score = np.round(
                    100.0
                    * account.passed_coding.count()
                    / (account.passed_coding.count() + account.failed_coding.count() + account.untested_coding.count())
                )
            except (ValueError, ZeroDivisionError):
                account.coding_score = None
        Account.objects.bulk_update(accounts, ["coding_score"])
        # Now chain the next method since we've done the null update
        for account in accounts:
            if data[account.pk]:
                update_vitals_score.delay(account.pk, True)
    except Exception as err:
        logger.debug(f"Exception in update_coding_score: {err}")


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_vitals_score(requests):
    """Run the update on the account after a new viotals result has been set.

    Args:
        account (pk): primary key for account to update
        chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts
    try:
        accounts = Account.objects.filter(pk__in=list(data.keys()))
        for account in accounts:
            logger.debug(f"Updating VITALs for {account.username}")
            try:
                account.vitals_score = np.round(
                    100.0
                    * account.passed_vitals.count()
                    / (account.passed_vitals.count() + account.failed_vitals.count() + account.untested_vitals.count())
                )
            except (ValueError, ZeroDivisionError):
                account.vitals_score = None
        Account.objects.bulk_update(accounts, ["vitals_score"])
        # Now chain the next method since we've done the null update
        for account in accounts:
            if data[account.pk]:
                update_engagement.delay(account.pk, True)
    except Exception as err:
        logger.debug(f"Exception in update_vitals_score: {err}")


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_engagement(requests):
    """Run the update on the account after a new attendance has been set.

    Args:
       account (pk): primary key for account to update
       chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts
    try:
        accounts = Account.objects.filter(pk__in=list(data.keys()))
        for account in accounts:
            if (phas1000 := account.module_enrollments.filter(module__code=config.TUTORIAL_MODULE)).count() > 0:
                cohort = phas1000.first().module.year
            else:  # No point updating engagement if student not registered on PHAS1000
                continue

            try:
                logger.debug(f"Updating engagement score for {account.username}")
                record = (
                    np.array(
                        account.tutorial_sessions.filter(session__cohort=cohort)
                        .order_by("-session__start")
                        .values_list("score")
                    )
                    .ravel()
                    .astype(float)
                )
                if record.size > 0:
                    record = np.where(record < 0, np.nan, record)
                    record = np.where(record == 2, 3, record)  # Good and excellent engagement should count the same
                    weight = np.exp(-np.arange(len(record)) / config.ENGAGEMENT_TC)
                    perfect = (3 * np.ones_like(record) * weight)[~np.isnan(record)].sum()
                    actual = (record * weight)[~np.isnan(record)].sum()
                    result = np.round(100 * actual / perfect, 1)
                else:
                    result = None

                account.engagement = result
            except (ValueError, ZeroDivisionError):
                account.engagement = None
        Account.objects.bulk_update(accounts, ["engagement"])
        for account in accounts:
            if data[account.pk]:
                update_activity.delay(account.pk, True)
    except Exception as err:
        logger.debug(f"Exception in update_engagement: {err}")


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_activity(requests):
    """Run the update on the account after a new results and attendance has been set.

    Args:
       account (pk): primary key for account to update
       chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts
    try:
        accounts = Account.objects.filter(pk__in=list(data.keys()))
        for account in accounts:
            try:
                logger.debug(f"Updating overall activity score for {account.username}")
                hw = account.tests_score
                if not isinstance(hw, float) or np.isnan(hw):
                    hw = 100.0
                lb = account.labs_score
                if not isinstance(lb, float) or np.isnan(lb):
                    lb = 100.0
                ct = account.coding_score
                if not isinstance(ct, float) or np.isnan(ct):
                    ct = 100.0
                vt = account.vitals_score
                if not isinstance(vt, float) or np.isnan(vt):
                    vt = 100.0
                tt = account.engagement
                if not isinstance(tt, float) or np.isnan(tt):
                    tt = 100.0
                account.activity_score = np.round(
                    (
                        config.TESTS_WEIGHT * hw
                        + config.LABS_WEIGHT * lb
                        + config.CODING_WEIGHT * ct
                        + config.VITALS_WEIGHT * vt
                        + config.TUTORIALS_WEIGHT * tt
                    )
                    / (
                        config.TESTS_WEIGHT
                        + config.LABS_WEIGHT
                        + config.CODING_WEIGHT
                        + config.VITALS_WEIGHT
                        + config.TUTORIALS_WEIGHT
                    )
                )
            except (ValueError, ZeroDivisionError):
                continue
        Account.objects.bulk_update(accounts, ["activity_score"])
    except Exception as err:
        logger.debug(f"Exception in update_activity: {err}")


@celery_app.task
def update_all_users():
    """Update all user accounts.

    This task should be run daily, probably after the minerva import task to update all the users with vurrent tests
    and vitals.

    Use celery-batches and DjangoTask to allow us to discard multiple requests for greater efficiency.
    """
    logger.debug("Running update all users task")
    try:
        for account in Account.objects.all():
            update_tests_score.delay(account.pk, True)
    except Exception as err:
        logger.debug(f"Exception in update_all_users: {err}")


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
        for vital_r in account.vital_results.filter(passed=True):
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
    logger.debug(f"Toal of {len(missing)} unexpected VITAL passes.")
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
