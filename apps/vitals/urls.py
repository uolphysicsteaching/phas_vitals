# -*- coding: utf-8 -*-
"""URL mapping for minerva app."""
# Django imports
from django.urls import path

# app imports
from . import views

urlpatterns = [
    path("vitals_view/", views.ShowVitralResultsView.as_view()),
    path("detail/<pk>/", views.VitalDetailView.as_view()),
]
