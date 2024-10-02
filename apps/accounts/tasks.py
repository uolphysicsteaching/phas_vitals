# -*- coding: utf-8 -*-
"""Celery tasks for the accounts app."""
# Python imports
import logging

# Django imports
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied

# external imports
import numpy as np
from celery import shared_task
from celery_batches import Batches
from constance import config
from django_auth_adfs.config import provider_config

# app imports
from phas_vitals import celery_app
from phas_vitals.celery import PHASTask

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


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_labs_score(requests):
    """Run the update on the account after a new test score has been set.

    Args:
        account (pk): primary key for account to update
        chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts

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


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_coding_score(requests):
    """Run the update on the account after a new test score has been set.

    Args:
        account (pk): primary key for account to update
        chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts

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


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_vitals_score(requests):
    """Run the update on the account after a new viotals result has been set.

    Args:
        account (pk): primary key for account to update
        chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts

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


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_engagement(requests):
    """Run the update on the account after a new attendance has been set.

    Args:
       account (pk): primary key for account to update
       chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts

    accounts = Account.objects.filter(pk__in=list(data.keys()))
    for account in accounts:
        if (phas1000 := account.module_enrollments.filter(module__code=config.TUTORIAL_MODULE)).count() > 0:
            cohort = phas1000.first().module.year
        else:  # No point updating engagement if student not registered on PHAS1000
            continue

        try:
            logger.debug(f"Updating engagement score for {account.username}")
            record = np.array(
                account.tutorial_sessions.filter(session__cohort=cohort)
                .order_by("-session__start")
                .values_list("score")
            )
            if record.size > 0:
                record = record[:, 0].astype(float)

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


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_activity(requests):
    """Run the update on the account after a new results and attendance has been set.

    Args:
       account (pk): primary key for account to update
       chain next task (bool): If True, call the next task for this account.
    """
    data = {request.args[0]: request.args[1] for request in requests}  # Use dict keys to de-dupl;icate accounts

    accounts = Account.objects.filter(pk__in=list(data.keys()))
    for account in accounts:
        try:
            logger.debug(f"Updating overall activity score for {account.username}")
            hw = account.tests_score
            if not isinstance(hw, float):
                hw = 100.0
            lb = account.labs_score
            if not isinstance(lb, float):
                lb = 100.0
            ct = account.coding_score
            if not isinstance(ct, float):
                ct = 100.0
            vt = account.vitals_score
            if not isinstance(vt, float):
                vt = 100.0
            tt = account.engagement
            if not isinstance(tt, float):
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


@celery_app.task
def update_all_users():
    """Update all user accounts.

    This task should be run daily, probably after the minerva import task to update all the users with vurrent tests
    and vitals.

    Use celery-batches and DjangoTask to allow us to discard multiple requests for greater efficiency.
    """
    logger.debug("Running update all users task")
    for account in Account.objects.all():
        update_tests_score.delay(account.pk, True)


@shared_task()
def update_user_from_graph(user_pk, obo_access_token):
    """Use MSGraph API to update a user account."""
    # At the moment I don't have outgoing msgraph.com I think
    url = "https://graph.microsoft.com/v1.0/me?$select=employeeId"
    logger.debug(f"Starting MS Graph call for {user_pk}")
    try:
        user = Account.objects.get(pk=user_pk)
    except ObjectDoesNotExist:
        logger.debug("No such user {user_pk} giving up.")
        return

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
    user.number = int(payload["employeeId"])
