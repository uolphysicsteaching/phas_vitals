# Python imports
import sys
import socket
from pathlib import Path

# Import some utility functions

# #########################################################

# ##### Setup system path to include usr/local packages
# Import some utility functions

major, minor = sys.version_info[0:2]
sys.path.append(f"/usr/local/lib/python{major}.{minor}/site-packages")

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
# This is an internal setting, used in the TEMPLATES directive
PROJECT_TEMPLATES = [
    str(PROJECT_ROOT_PATH / "templates"),
]

# add apps/ to the Python path
sys.path.append((PROJECT_ROOT_PATH / "apps").absolute())


# ##### APPLICATION CONFIGURATION #########################

APPS = {
    f.name: f
    for f in (PROJECT_ROOT_PATH / "apps").iterdir()
    if f.is_dir() and not f.name.startswith(".") and (f / "models.py").exists()
}


# This are the apps
CUSTOM_APPS = list(APPS.keys())
# Autobuild all
appdirs = list(APPS.items())
print("#" * 80)
for app in APPS:
    print(f"Adding {app=}")
print("#" * 80)


# these are the apps
DEFAULT_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
] + CUSTOM_APPS

# Middlewares
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.flatpages.middleware.FlatpageFallbackMiddleware",
]

# Template stuff
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": PROJECT_TEMPLATES,
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "constance.context_processors.config",
                "django.template.context_processors.request",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
            ],
            "builtins": [
                "django.templatetags.static",
                "mathfilters.templatetags.mathfilters",
            ],
        },
    }
]


# Internationalization
USE_I18N = False


# ##### SECURITY CONFIGURATION ############################

# We store the secret key here
# The required SECRET_KEY is fetched at the end of this file
SECRET_FILE = (PROJECT_ROOT_PATH/"run"/"SECRET.key").absolute()

# these persons receive error notification
ADMINS = (("[[ your name ]]", "[[ your_name@example.com ]]"),)
MANAGERS = ADMINS


# ##### DJANGO RUNNING CONFIGURATION ######################

# the default WSGI application
WSGI_APPLICATION = f"{SITE_NAME}.wsgi.application"

# the root URL configuration
ROOT_URLCONF = f"{SITE_NAME}.urls"

# This site's ID
SITE_ID = 1

# The URL for static files
STATIC_URL = "/static/"

# the URL for media files
MEDIA_URL = "/media/"

# ##### Settings for CSRF protection
try:
    DNS_NAME = f"{SITE_NAME}.your.domain.name"
    IP_ADDR = socket.gethostbyname(DNS_NAME)
except socket.gaierror:
    DNS_NAME = "loxcalhost"
    IP_ADDR = "127.0.0.1"

ALLOWED_HOSTS = [DNS_NAME, IP_ADDR, "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = [f"https://{x}" for x in ALLOWED_HOSTS]

# #### Session Settings

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 7200  # 2 hours before login again

# ##### Login settings

HTTPS_SUPPORT = True
SECURE_REQUIRED_PATHS = ("/login",)

# ##### Default autofield type

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# ##### DEBUG CONFIGURATION ###############################
DEBUG = False


# ##### INTERNATIONALIZATION ##############################

LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/London"

# Internationalization
USE_I18N = True

# Localisation
USE_L10N = True

# enable timezone awareness by default
USE_TZ = True


# Finally grab the SECRET KEY
try:
    SECRET_KEY = SECRET_FILE.read_text().strip()
except IOError:
    try:
        from django.utils.crypto import get_random_string

        chars = "abcdefghijklmnopqrstuvwxyz0123456789!$%&()=+-_"
        SECRET_KEY = get_random_string(50, chars)
        SECRET_FILE.write_text(SECRET_KEY)
    except IOError:
        raise Exception("Could not open %s for writing!" % SECRET_FILE)

# LOGGING config

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": str(PROJECT_ROOT_PATH/"logs"/"django.log"),
        },
        "file_info": {
            "class": "logging.FileHandler",
            "filename": str(PROJECT_ROOT_PATH/"logs"/"form_data.log"),
        },
        "mail_admins": {"level": "ERROR", "class": "django.utils.log.AdminEmailHandler"},
    },
    "formatters": {"verbose": {"format": "%(asctime)s %(levelname)-8s [%(name)s:%(lineno)s] %(message)s"}},
    "loggers": {
        "": {"handlers": ["file"], "level": "DEBUG", "propagate": True},
        "auth": {"handlers": ["file"], "level": "INFO", "propagate": True},
        "django.request": {"handlers": ["mail_admins"], "level": "ERROR", "propagate": True},
        "django.security": {"handlers": ["mail_admins"], "level": "ERROR", "propagate": True},
        "phys_utils.middleware": {
            "handlers": ["file_info"],
            "propagate": False,
        },
    },
}

####### EMAIL SETTINGS ####################################

EMAIL_HOST = ADMINS[0][1]
EMAIL_PORT = 587
EMAIL_SUBJECT_PREFIX = f"{SITE_NAME} :"
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = f"no-reply@{DNS_NAME}"


# Import Applicaton-specific Settings
for app in CUSTOM_APPS:
    try:
        app_module = __import__(app, globals(), locals(), ["settings"])
        app_settings = getattr(app_module, "settings", None)
        for setting in dir(app_settings):
            if setting == setting.upper():
                set_val = getattr(app_settings, setting)
                if isinstance(set_val, dict):  # Merge app.seetings
                    locals()[setting].update(set_val)
                elif isinstance(set_val, (list, tuple)):  # append app.settings
                    locals()[setting] = locals()[setting] + set_val
                else:  # replace with app.settings
                    locals()[setting] = set_val
    except ImportError:
        pass
