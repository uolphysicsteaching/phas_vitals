# -*- coding: utf-8 -*-
"""Celery tasks for the accounts app."""
# Python imports
import logging

# Django imports
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied

# external imports
import numpy as np
from celery import shared_task
from constance import config
from django_auth_adfs.config import provider_config

# app imports
from phas_vitals.celery import PHASTask

# app imports
from .models import Account

logger = logging.getLogger(__file__)


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_tests_score(requests):
    """Run the update on the account after a new test score has been set."""
    ids = list(set([request.args[0] for request in requests]))  # Pass through set deduplicates account.pk values
    accounts = Account.objects.filter(pk__in=ids)
    for account in accounts:
        try:
            account.tests_score = np.round(
                100.0
                * account.passed_tests.count()
                / (account.passed_tests.count() + account.failed_tests.count() + account.untested_tests.count())
            )
        except (ValueError, ZeroDivisionError):
            account.tests_score = None
    Account.objects.bulk_update(accounts, ["tests_score"])


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_labs_score(requests):
    """Run the update on the account after a new test score has been set."""
    ids = list(set([request.args[0] for request in requests]))  # Pass through set deduplicates account.pk values
    accounts = Account.objects.filter(pk__in=ids)
    for account in accounts:
        try:
            account.labs_score = np.round(
                100.0
                * account.passed_labs.count()
                / (account.passed_labs.count() + account.failed_labs.count() + account.untested_labs.count())
            )
        except (ValueError, ZeroDivisionError):
            account.labs_score = None
    Account.objects.bulk_update(accounts, ["labs_score"])


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_vitals_score(requests):
    """Run the update on the account after a new viotals result has been set."""
    ids = list(set([request.args[0] for request in requests]))  # Pass through set deduplicates account.pk values
    accounts = Account.objects.filter(pk__in=ids)
    for account in accounts:
        try:
            account.vitals_score = np.round(
                100.0
                * account.passed_vitals.count()
                / (account.passed_vitals.count() + account.failed_vitals.count() + account.untested_vitals.count())
            )
        except (ValueError, ZeroDivisionError):
            account.vitals_score = None
    Account.objects.bulk_update(accounts, ["vitals_score"])


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_engagement(requests):
    """Run the update on the account after a new attendance has been set."""
    ids = list(set([request.args[0] for request in requests]))  # Pass through set deduplicates account.pk values
    accounts = Account.objects.filter(pk__in=ids)
    for account in accounts:
        try:
            record = np.array(
                account.tutorial_sessions.filter(session__cohort=account.cohort)
                .order_by("-session__start")
                .values_list("score")
            )
            if record.size > 0:
                record = record[:, 0].astype(float)

                record = np.where(record < 0, np.nan, record)
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


@shared_task(base=PHASTask, flush_every=100, flush_interval=10)
def update_all_users(requests):
    """Update all user accounts.

    This task should be run daily, probably after the minerva import task to update all the users with vurrent tests
    and vitals.

    Use celery-batches and DjangoTask to allow us to discard multiple requests for greater efficiency.
    """
    for account in Account.objects.all():
        update_tests_score.delay(account.pk)
        update_vitals_score.delay(account.pk)
        update_engagement.delay(account.pk)
        update_labs_score.delay(account.pk)


@shared_task
def update_user_from_graph(user_pk, obo_access_token):
    """Use MSGraph API to update a user account."""
    # At the moment I don't have outgoing msgraph.com I think
    url = "https://graph.microsoft.com/v1.0/me?$select=employeeId"
    try:
        user = Account.objects.get(pk=user_pk)
    except ObjectDoesNotExist:
        return

    headers = {"Authorization": "Bearer {}".format(obo_access_token)}
    response = provider_config.session.get(url, headers=headers, timeout=30, verify=False)

    if response.status_code in [400, 401]:
        logger.error(f"MS Graph server returned an error: {response.json()['message']}")
        raise PermissionDenied

    if response.status_code != 200:
        logger.error("Unexpected MS Graph response: {response.content.decode()}")
        raise PermissionDenied

    payload = response.json()
    user.number = int(payload["employeeId"])
