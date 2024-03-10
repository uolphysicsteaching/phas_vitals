# -*- coding: utf-8 -*-
"""URL mapping for minerva app."""
# Django imports
from django.urls import path

# app imports
from . import views

urlpatterns = [
    path("import_tests/", views.ImportTestsView.as_view()),
    path("import_tests_stream/", views.StreamingImportTestsView.as_view()),
    path("import_history/", views.ImportTestHistoryView.as_view()),
    path("import_history_stream/", views.StreamingImportTestsHistoryView.as_view()),
    path("test_view/", views.ShowTestResults.as_view()),
    path("generate_marksheet/", views.GenerateModuleMarksheetView.as_view()),
    path("detail/<pk>/", views.TestDetailView.as_view()),
]
