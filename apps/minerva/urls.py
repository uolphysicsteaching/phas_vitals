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
    path("import_tests/", views.ImportTestsView.as_view()),
    path("import_tests_stream/", views.StreamingImportTestsView.as_view()),
    path("import_history/", views.ImportTestHistoryView.as_view()),
    path("import_history_stream/", views.StreamingImportTestsHistoryView.as_view()),
    path("test_view/", views.ShowTestResults.as_view()),
    path("test_barchart/", views.TestResultsBarChartView.as_view(), name="test-barchart"),
    path("generate_marksheet/", views.GenerateModuleMarksheetView.as_view()),
    path(
        "generate_performance_spreadsheet/",
        views.StudentPerformanceSpreadsheetView.as_view(),
        name="student_performance",
    ),
    path("detail/<pk>/", views.TestDetailView.as_view()),
    path("dal_modules/", views.ModuleAutocomplete.as_view(), name="Module_lookup"),
    path("dal_tests/", views.TestAutocomplete.as_view(), name="Test_lookup"),
]
