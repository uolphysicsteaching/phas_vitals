# Python imports

# app imports
# project imports
from .secrets import *  # NOQA  pylint: disable=unused-import

# uncomment the following line to include i18n
# from .i18n import *


# ##### DEBUG CONFIGURATION ###############################
DEBUG = False

# allow all hosts during development
ALLOWED_HOSTS = ["*"]

# adjust the minimal login
LOGIN_URL = "core_login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "core_login"


# ##### APPLICATION CONFIGURATION #########################

INSTALLED_APPS = DEFAULT_APPS
