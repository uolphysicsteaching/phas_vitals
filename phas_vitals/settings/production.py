"""Production mode settings."""

# app imports
from .common import *  # NOQA  pylint: disable=unused-import,wildcard-import
from .secrets import *  # NOQA  pylint: disable=unused-import,wildcard-import

DEBUG = False

SECURE_HSTS_SECONDS = 3600
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
