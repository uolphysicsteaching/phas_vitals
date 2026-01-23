"""Test settings for pytest."""

# Python imports
import sys
from pathlib import Path

# ##### PATH CONFIGURATION ################################

# fetch Django's project directory
DJANGO_ROOT_PATH = Path(__file__).parent.parent
DJANGO_ROOT = str(DJANGO_ROOT_PATH)

# fetch the project_root
PROJECT_ROOT_PATH = DJANGO_ROOT_PATH.parent
PROJECT_ROOT = str(PROJECT_ROOT_PATH)

# the name of the whole site
SITE_NAME = DJANGO_ROOT_PATH.name

# collect static files here
STATIC_ROOT = str(PROJECT_ROOT_PATH / "run" / "static")

# collect media files here
MEDIA_ROOT = str(PROJECT_ROOT_PATH / "run" / "media")

# look for static assets here
STATICFILES_DIRS = [
    str(PROJECT_ROOT_PATH / "static"),
]

# look for templates here
PROJECT_TEMPLATES = [
    str(PROJECT_ROOT_PATH / "templates"),
]

# Add apps to path
APPS_PATH = PROJECT_ROOT_PATH / "apps"
sys.path.append(str(APPS_PATH.absolute()))

# Test database configuration
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

# ##### APPLICATION CONFIGURATION #########################
# Minimal apps for testing
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party apps needed by models
    "sitetree",
    # Custom apps
    "accounts",
    "minerva",
    "vitals",
    "util",
    "psrb",
    "tutorial",
    "htmx_views",
]

# ##### MIDDLEWARE #########################################
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ##### TEMPLATES #########################################
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": PROJECT_TEMPLATES,
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ##### SITE CONFIGURATION #################################
SITE_ID = 1

# ##### AUTH CONFIGURATION #################################
AUTH_USER_MODEL = "accounts.Account"
ROOT_URLCONF = "phas_vitals.urls"

# ##### STATIC FILES CONFIGURATION ########################
STATIC_URL = "/static/"

# ##### MEDIA FILES CONFIGURATION #########################
MEDIA_URL = "/media/"

# ##### LOGGING CONFIGURATION #############################
# Simple logging configuration for tests
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
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ##### CONSTANCE CONFIGURATION ###########################
# Mock constance configuration for testing
CONSTANCE_BACKEND = "constance.backends.memory.MemoryBackend"
CONSTANCE_CONFIG = {
    "SUBJECT_PREFIX": ("PHAS", "Subject prefix for module codes"),
    "LAB_PATTERN": (r"(?P<name>Lab \d+)", "Lab pattern"),
    "HOMEWORK_PATTERN": (r"(?P<name>HW \d+)", "Homework pattern"),
    "CODE_PATTERN": (r"(?P<name>Code \d+)", "Code pattern"),
}

# ##### TIME ZONE CONFIGURATION ###########################
USE_TZ = True
TIME_ZONE = "UTC"

# ##### INTERNATIONALIZATION ##########################
USE_I18N = True
LANGUAGE_CODE = "en-gb"
