# -*- coding: utf-8 -*-
"""Ensure dnb operations happen on post-migrate."""
# Django imports
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# app imports
from .models import Account


@receiver(post_migrate)
def create_custom_permission(sender, **kwargs):
    """Create the permissions needed."""
    content_type = ContentType.objects.get_for_model(Account)
    Permission.objects.get_or_create(
        codename="is_tutor",
        name="Can Update Tutorial Attendance",
        content_type=content_type,
    )
    Permission.objects.get_or_create(
        codename="is_superuser",
        name="Can Review Whole Cohort",
        content_type=content_type,
    )
