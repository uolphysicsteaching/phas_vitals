# Import some utility functions
from os.path import join
# Fetch our common settings
from common import *

# #########################################################

# ##### DEBUG CONFIGURATION ###############################
DEBUG = True


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
