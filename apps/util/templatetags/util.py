# -*- coding: utf-8 -*-
"""Custom templatetags."""

# Python imports
import urllib.parse

# Django imports
from django import template
from django.db.models import Model

register = template.Library()


@register.simple_tag
def urlencoded_form_data(form):
    """
    A template tag to urlencode all form data.
    """
    if form.is_valid():
        data = form.cleaned_data
    else:
        # Use raw data if the form is not valid
        data = form.data

    data.update({k: v.pk for k, v in data.items() if isinstance(v, Model)})
    # urlencode the form data
    return urllib.parse.urlencode(data)
