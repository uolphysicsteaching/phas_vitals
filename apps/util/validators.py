# -*- coding: utf-8 -*-
"""
Created on Tue May 21 21:21:37 2024

@author: phygbu
"""
# Django imports
from django.core.validators import BaseValidator
from django.utils.deconstruct import deconstructible


@deconstructible
class RangeValueValidator(BaseValidator):

    """A validator for a range of numbers."""

    code = "range_value"

    @property
    def message(self):
        """Return a limit message."""
        return f"Ensure value is between {self.limit_value[0]} and {self.limit_value[1]}"

    def compare(self, a, b):
        return a is None or min(b) <= a <= max(b)
