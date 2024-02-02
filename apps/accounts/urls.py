# Python imports
from os.path import basename, dirname

# Django imports
from django.urls import path, re_path

# app imports
from . import views

app_name = basename(dirname(__file__))

urlpatterns = []
