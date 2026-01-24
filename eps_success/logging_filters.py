# -*- coding: utf-8 -*-
"""Custom Log Filtering to remove noisy exceptions."""

# Python imports
import logging

# Django imports
from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.urls import NoReverseMatch


class IgnoreNoiseFilter(logging.Filter):
    def filter(self, record):
        if record.exc_info:
            exc_type, _, _ = record.exc_info
            if not settings.DEBUG and (exc_type is DisallowedHost or exc_type is NoReverseMatch):
                return False
        return True
