# -*- coding: utf-8 -*-
"""Field Validators used in the code base."""
# Django imports
from django.core.validators import BaseValidator
from django.utils.deconstruct import deconstructible


@deconstructible
class RangeValueValidator(BaseValidator):
    """A validator for a range of numbers."""

    code = "range_value"

    @property
    def message(self):
        """Return limit message."""
        return f"Ensure {self.value} is between {self.limit_value[0]} and {self.limit_value[1]}"

    def compare(self, a, b):
        """Check where a is None or between the limits given in b."""
        ret = a is None or min(b) <= a <= max(b)
        self.value = a
        return not ret
