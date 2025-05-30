# Python imports
from os.path import join

# Django imports
from django.utils.translation import gettext_lazy as _

# app imports
# project imports
from .common import MIDDLEWARE, PROJECT_ROOT

# ##### INTERNATIONALIZATION ##############################

LANGUAGE_CODE = "de"
TIME_ZONE = "Europe/Berlin"

# Internationalization
USE_I18N = True

# Localisation

# enable timezone awareness by default
USE_TZ = True

# This list of languages will be provided
LANGUAGES = (("en", _("English")), ("de", _("German")))

# Look for translations in these locations
LOCALE_PATHS = (join(PROJECT_ROOT, "locale"),)

# Inject the localization middleware into the right position
MIDDLEWARE = [
    y
    for i, x in enumerate(MIDDLEWARE)
    for y in (
        ("django.middleware.locale.LocaleMiddleware", x)
        if MIDDLEWARE[i - 1] == "django.contrib.sessions.middleware.SessionMiddleware"
        else (x,)
    )
]
