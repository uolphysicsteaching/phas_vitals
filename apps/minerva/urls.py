# -*- coding: utf-8 -*-
"""URL mapping for minerva app."""
# Django imports
from django.urls import path

# app imports
from . import views

urlpatterns = [
    path("import_tests/", views.ImportTestsView.as_view()),
    path("import_history/", views.ImportTestHistoryView.as_view()),

    
]

