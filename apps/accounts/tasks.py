# -*- coding: utf-8 -*-
"""Celery tasks for the accounts app."""
# external imports
import numpy as np
from celery import shared_task
from celery_batches import Batches

# app imports
from .models import Account


@shared_task(base=Batches, flush_every=100, flush_interval=10)
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


@shared_task(base=Batches, flush_every=100, flush_interval=10)
def update_vitals_score(requests):
    """Run the update on the account after a new test score has been set."""
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


@shared_task
def update_all_users():
    """Update all user accounts.

    This task should be run daily, probably after the minerva import task to update all the users with vurrent tests
    and vitals."""
    for account in Account.objects.all():
        update_tests_score.delay(account.pk)
        update_vitals_score.delay(account.pk)
