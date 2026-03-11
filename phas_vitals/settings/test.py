"""Test settings for pytest.

Imports base settings from common.py and overrides with test-specific configuration.
"""

# app imports
from .common import *  # NOQA

# ##### TEST DATABASE CONFIGURATION #######################
# Override database to use in-memory SQLite for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ##### DEBUG CONFIGURATION ###############################
DEBUG = True
TESTING = True

# allow all hosts during testing
ALLOWED_HOSTS = ["*", "testserver"]

# ##### SECRET KEY #########################################
SECRET_KEY = "test-secret-key-for-testing-only"

# ##### SITETREE CONFIGURATION ############################
# Disable the custom SiteTree class to avoid the circular-import that arises
# when util.tree is loaded while sitetree.sitetreeapp is still being imported.
SITETREE_CLS = None

# ##### APPLICATION CONFIGURATION #########################
# Use minimal apps for testing to avoid complex dependency issues
# Note: django.contrib.admin and baton are excluded
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party apps needed by models
    "sitetree",
] + CUSTOM_APPS

# ##### LOGGING CONFIGURATION #############################
# Disable logging for tests
LOGGING_CONFIG = None
LOGGING = {}

# ##### CELERY CONFIGURATION ##############################
# Use synchronous task execution for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# ##### EMAIL CONFIGURATION ###############################
# Use console email backend for testing
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ##### CACHE CONFIGURATION ###############################
# Use local memory cache for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ##### CONSTANCE CONFIGURATION ###########################
# Use memory backend for constance in tests
CONSTANCE_BACKEND = "constance.backends.memory.MemoryBackend"

# ##### PROJECT-SPECIFIC CONFIGURATION ####################
# These settings may not be defined in common.py but are needed by models

# Semesters configuration (if not in common.py)
if "SEMESTERS" not in globals():
    SEMESTERS = [(1, "Semester 1"), (2, "Semester 2"), (3, "Both Semesters")]

# Tutorial marks configuration (if not in common.py)
if "TUTORIAL_MARKS" not in globals():
    TUTORIAL_MARKS = [
        (0, "Not Attended", "silver"),
        (1, "Absent", "tomato"),
        (2, "Attended", "springgreen"),
        (3, "Engaged", "mediumseagreen"),
        (4, "Excellent", "forestgreen"),
    ]

# VITALs results mapping (if not in common.py)
if "VITALS_RESULTS_MAPPING" not in globals():
    VITALS_RESULTS_MAPPING = {
        "passed": ("Passed", "green"),
        "failed": ("Failed", "red"),
        "pending": ("Pending", "yellow"),
    }
