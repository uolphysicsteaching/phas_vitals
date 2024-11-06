# -*- coding: utf-8 -*-
"""Util app views."""

# Django imports
from django.urls import path

# app imports
from .views import StaffUserTemplateView, SuperuserTemplateView
from .wizard import GradebookImport

urlpatterns = [
    path("tools/", SuperuserTemplateView.as_view(template_name="util/tools.html")),
    path("data/", StaffUserTemplateView.as_view(template_name="util/data.html")),
    path(
        "gradebook/",
        GradebookImport.as_view(
            GradebookImport.forms,
        ),
        name="module_gradecentre",
    ),
]
