# -*- coding: utf-8 -*-
"""Field Validators used in the code base."""
# Django imports
from django.core.validators import BaseValidator
from django.utils.deconstruct import deconstructible

# external imports
from numpy import isnan


@deconstructible
class RangeValueValidator(BaseValidator):
    """Validates a number as None, nan or between upper and lower limits."""

    message = "Ensure this value is None, NaN, or between 0.0 and 100.0 inclusive."
    code = "invalid_float_range"

    def __init__(self, limit_value=None, message=None):
        """Set default limit range tro 0...100."""
        if limit_value is None:
            limit_value = (0.0, 100.0)
        super().__init__(limit_value, message=message)

    def compare(self, value, _):
        if value is None:
            return False
        if isinstance(value, float) and isnan(value):
            return False
        return not (min(self.limit_value) <= value <= max(self.limit_value))

    def clean(self, value):
        return value  # No transformation needed
