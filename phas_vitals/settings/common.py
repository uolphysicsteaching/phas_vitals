# Python imports
import re
import socket
import sys
from importlib import import_module
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

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ##### APPLICATION CONFIGURATION #########################

APPS = {
    f.name: f
    for f in (PROJECT_ROOT_PATH / "apps").iterdir()
    if f.is_dir() and not f.name.startswith(".") and (f / "models.py").exists()
}

APPS_PATH = PROJECT_ROOT_PATH / "apps"

sys.path.append(str(APPS_PATH.absolute()))

appdirs = [APPS_PATH / x for x in APPS_PATH.glob("*") if (APPS_PATH / x).is_dir()]

# This are the apps
CUSTOM_APPS = []
# Autobuild all
print("#" * 80)
for appdir in appdirs:
    if (appdir / "models.py").exists():  # Only add apps that have a models.py
        print(f"Adding app {appdir.name}")
        CUSTOM_APPS.append(appdir.name)
print("#" * 80)

# these are the apps
DEFAULT_APPS = (
    [
        "baton",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.flatpages",
        "django.contrib.sessions",
        "django.contrib.sites",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        ### General 3rd party apps
        "adminsortable2",
        "ajax_select",
        "colorful",  # django-colorful package
        "constance",
        "cookielaw",
        "corsheaders",
        "dal",
        "dal_select2",
        "django_bootstrap5",
        "django_extensions",
        "django_filters",
        "django_tables2",
        "email_obfuscator",
        "floppyforms",
        "import_export",
        "mathfilters",
        "oauth2_provider",
        "rest_framework",
        "sitetree",  # django-sitetree package
        "smart_selects",
        "tinymce",  # django-tinymce package
    ]
    + CUSTOM_APPS
    + [
        "baton.autodiscover",
    ]
)

# Middlewares
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
SECRET_FILE = (PROJECT_ROOT_PATH / "run" / "SECRET.key").absolute()

# these persons receive error notification
ADMINS = (("Gavin  Burnell", "G.Burnell@leeds.ac.uk"),)
MANAGERS = ADMINS

####### User model and Authentication #####################

AUTH_USER_MODEL = "accounts.Account"

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
    DNS_NAME = f"{SITE_NAME}.leeds.ac.uk"
    IP_ADDR = socket.gethostbyname(DNS_NAME)
except socket.gaierror:
    DNS_NAME = "localhost"
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

# only use TemporaryFileUploadHandler for file uploads
FILE_UPLOAD_HANDLERS = ("django.core.files.uploadhandler.TemporaryFileUploadHandler",)

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
        # Django imports
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
            "filename": str(PROJECT_ROOT_PATH / "logs" / "django.log"),
        },
        "file_info": {
            "class": "logging.FileHandler",
            "filename": str(PROJECT_ROOT_PATH / "logs" / "form_data.log"),
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

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.leeds.ac.uk"
EMAIL_PORT = 25
EMAIL_USE_TLS = False
DEFAULT_FROM_EMAIL = f"no-reply@{SITE_NAME}.leeds.ac.uk"


####### GRAPPELI Settings ##################################

GRAPPELLI_ADMIN_TITLE = "Physics VITALS management"
GRAPPELLI_SWITCH_USER = True

###### Constance Settings ##################################

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

CONSTANCE_IGNORE_ADMIN_VERSION_CHECK = True

CONSTANCE_CONFIG = {
    "SUBJECT_PREFIX": ("PHAS", "Module Subject code prefix"),
}

CONSTANCE_ADDITIONAL_FIELDS = {
    "custdatetime": [
        "django.forms.fields.SplitDateTimeField",
        {
            "widget": "django.forms.widgets.SplitDateTimeWidget",
            "input_date_formats": ["%Y-%m-%d"],
            "input_time_formats": ["%H:%M:%S"],
        },
    ]
}

###### BATON Configuration ###############################

BATON = {
    "SITE_HEADER": "Physics VITALS tracking",
    "SITE_TITLE": "Physics VITALS",
    "INDEX_TITLE": "Site administration",
    #'SUPPORT_HREF': 'https://github.com/otto-torino/django-baton/issues',
    "COPYRIGHT": "copyright © 2023 University of Leeds",
    #'POWERED_BY': '<a href="https://www.otto.to.it">Otto srl</a>',
    "CONFIRM_UNSAVED_CHANGES": True,
    "SHOW_MULTIPART_UPLOADING": True,
    "ENABLE_IMAGES_PREVIEW": True,
    "CHANGELIST_FILTERS_IN_MODAL": True,
    "CHANGELIST_FILTERS_ALWAYS_OPEN": False,
    "CHANGELIST_FILTERS_FORM": True,
    "COLLAPSABLE_USER_AREA": False,
    "MENU_ALWAYS_COLLAPSED": False,
    "MENU_TITLE": "Menu",
    "MESSAGES_TOASTS": False,
    "GRAVATAR_DEFAULT_IMG": "retro",
    "GRAVATAR_ENABLED": True,
    "FORCE_THEME": None,
    #'LOGIN_SPLASH': '/static/core/img/login-splash.png',
    # 'SEARCH_FIELD': {
    #     'label': 'Search contents...',
    #     'url': '/search/',
    # },
    "MENU": (
        {"type": "title", "label": "main", "apps": ("auth",)},
        {
            "type": "app",
            "name": "accounts",
            "label": "AUsers and Accounts",
            "icon": "fa fa-users",
            "default_open": True,
            "models": (
                {"name": "account", "label": "Users"},
                {"name": "cohort", "label": "Student Cohorts"},
                {"name": "programme", "label": "Programmes"},
                {"name": "group", "label": "Groups"},
            ),
        },
        {
            "type": "app",
            "name": "minerva",
            "label": "Minerva Interaction",
            "icon": "fa fa-graduation-cap",
            "default_open": False,
            "models": (
                {"name": "module", "label": "Modules"},
                {"name": "moduleenrollment", "label": "Module Enroillments"},
                {"name": "test", "label": "Tests"},
                {"name": "test_score", "label": "Test Scores"},
                {"name": "test_attempt", "label": "Test Attempts"},
            ),
        },
        {
            "type": "app",
            "name": "vitals",
            "label": "VITALs",
            "icon": "fa fa-heartbeat",
            "default_open": False,
            "models": (
                {"name": "vital", "label": "VITALs"},
                {"name": "vital_result", "label": "VITAL Awards"},
                {"name": "vital_test_map", "label": "VITAL Test Maps"},
            ),
        },
        # { 'type': 'title', 'label': 'Contents', 'apps': ('flatpages', ) },
        # { 'type': 'model', 'label': 'Pages', 'name': 'flatpage', 'app': 'flatpages' },
        # { 'type': 'free', 'label': 'Custom Link', 'url': 'http://www.google.it', 'perms': ('flatpages.add_flatpage', 'auth.change_user') },
        # { 'type': 'free', 'label': 'My parent voice', 'children': [
        #     { 'type': 'model', 'label': 'A Model', 'name': 'mymodelname', 'app': 'myapp', 'icon': 'fa fa-gavel' },
        #     { 'type': 'free', 'label': 'Another custom link', 'url': 'http://www.google.it' },
        # ] },
    ),
    # 'ANALYTICS': {
    #     'CREDENTIALS': os.path.join(BASE_DIR, 'credentials.json'),
    #     'VIEW_ID': '12345678',
    # }
}

###### Django-extensions #################################

GRAPH_MODELS = {
    "all_applications": True,
    "group_models": True,
}


###### Django REST Framework Settings #####################

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAdminUser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "100/hour", "user": "1000/hour"},
}

###### Import config from apps ############################

_setting_pattern = re.compile("[A-Z][A-Z0-9_]+")
_app_pattern = re.compile("[a-z][a-z0-9_]+")

for app in CUSTOM_APPS:
    try:
        safe_app = _app_pattern.match(app).group(0)
    except AttributeError:
        breakpoint()
    try:  # Look for app.settings module
        # This looks like an untrusted import, but it's actually confied to apps living with ./apps/
        app_settings = import_module(safe_app + ".settings", __file__)  # nosemgrep
        for setting in dir(app_settings):
            if match := _setting_pattern.match(setting):  # settings are always ALL_CAPS_OR_DIGITS only
                set_val = getattr(app_settings, match.group(0))
                if isinstance(set_val, dict) and setting in locals():  # Merge app.settings if dictionary
                    locals()[match.group(0)].update(set_val)  # nosemgrep
                elif isinstance(set_val, (list, tuple)):  # append app.settings if list or tuple
                    locals()[match.group(0)] = locals()[setting] + set_val
                else:  # replace with app.settings
                    locals()[setting] = set_val
    except ImportError:
        pass
