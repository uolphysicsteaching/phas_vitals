# -*- coding: utf-8 -*-
"""Util app views."""

# Django imports
from django.urls import path

# app imports
from .views import SuperuserTemplateView

urlpatterns = [path("tools/", SuperuserTemplateView.as_view(template_name="util/tools.html"))]
