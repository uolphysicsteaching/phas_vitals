# -*- coding: utf-8 -*-
"""Import-Export Resources for util app."""
# external imports
from import_export import resources

# app imports
from .models import APIKey


class APIKeyResource(resources.ModelResource):
    """Import-export resource for APIKey objects."""

    class Meta:
        model = APIKey
