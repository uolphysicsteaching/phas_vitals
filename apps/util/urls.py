# -*- coding: utf-8 -*-
"""Util app views"""

from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path('tools/', TemplateView.as_view(template_name='util/tools.html'))
]
