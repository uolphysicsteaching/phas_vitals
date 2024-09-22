# -*- coding: utf-8 -*-
"""Settings for the util app."""
# Python imports
from datetime import datetime

# Django imports
from django.utils import timezone as tz

CONSTANCE_CONFIG = {
    "TASK_CLEANUP": (7, "Number of days to keep celery TaskResults", int),
    "HEARTBEAT": (tz.now(), "Last time the heartbeat was run", datetime),
}
