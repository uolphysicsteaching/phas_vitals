from __future__ import unicode_literals

from os.path import basename, dirname

from django.apps import AppConfig

class AccountsConfig(AppConfig):
    name = basename(dirname(__file__))
