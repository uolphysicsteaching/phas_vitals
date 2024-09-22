# -*- coding: utf-8 -*-
"""URL mapping for minerva app."""
# Python imports
from os.path import basename, dirname

# Django imports
from django.urls import path

# app imports
from . import views

app_name = basename(dirname(__file__))

urlpatterns = [
    path("vitals_view/", views.ShowVitralResultsView.as_view()),
    path("detail/<pk>/", views.VitalDetailView.as_view()),
    path("VITALlookup/", views.VITALAutocomplete.as_view(), name="VITAL_lookup"),
]
