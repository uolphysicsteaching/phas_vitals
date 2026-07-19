"""Production mode settings."""

# Python imports
from copy import deepcopy

# app imports
from .common import *  # NOQA  pylint: disable=unused-import,wildcard-import
from .secrets import *  # NOQA  pylint: disable=unused-import,wildcard-import

DEBUG = False

LOGGING = deepcopy(LOGGING)
LOGGING["root"]["level"] = "INFO"
LOGGING["handlers"]["file"]["level"] = "INFO"
LOGGING["handlers"]["htmx_file"]["level"] = "INFO"
LOGGING["handlers"]["file_info"]["level"] = "INFO"
LOGGING["handlers"]["file_debug"]["level"] = "INFO"
LOGGING["loggers"]["django_auth_adfs"]["level"] = "INFO"
LOGGING["loggers"]["celery_tasks"]["level"] = "INFO"
LOGGING["loggers"]["htmx_views.views"]["level"] = "INFO"

SECURE_HSTS_SECONDS = 3600
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
