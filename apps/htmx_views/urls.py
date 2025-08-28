# -*- coding: utf-8 -*-
"""urls for the hhtmx_views app."""
# Python imports
from os.path import basename, dirname

# Django imports
from django.urls import path

# app imports
from . import views

app_name = basename(dirname(__file__))
urlpatterns = [path("select/<str:lookup_channel>/", views.LinkedSelectEndpointView.as_view(), name="select")]
