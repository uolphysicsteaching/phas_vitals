# Python imports
from os.path import join

# project imports
from .common import *

# uncomment the following line to include i18n
# from .i18n import *


# ##### DEBUG CONFIGURATION ###############################
DEBUG = True

# allow all hosts during development
ALLOWED_HOSTS = ['*']

# adjust the minimal login
LOGIN_URL = 'core_login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'core_login'


# ##### DATABASE CONFIGURATION ############################
DATABASES = {
    'default': {
    #Settings for mysql on a centos server communicating locally over a unix port
    #Assumes DB and DB-user are both the site name - which is vaguely sensible.
        'ENGINE': 'django.db.backends.mysql',
        'NAME': SITE_NAME,
        'USER': SITE_NAME,
        'PASSWORD':'[[db password]]',
        'HOST':'/var/lib/mysql/mysql.sock',
        'PORT':'',
    }
}

# ##### APPLICATION CONFIGURATION #########################

INSTALLED_APPS = DEFAULT_APPS
