# -*- coding: utf-8 -*-
"""
Ensure that this file is in .gitignore !"""
from .common import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": SITE_NAME,
        "USER": SITE_NAME,
        "PASSWORD": "DBPASSED",
        "HOST": "DBHOST",
        "PORT": "5432",
    }
}
