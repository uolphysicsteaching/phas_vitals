"""Tests for VITAL handling in Minerva import-export resources."""

# Django imports
from django.db import IntegrityError, transaction

# external imports
import pytest
from vitals.models import VITAL

# app imports
from .resource import VITALsWidget


@pytest.mark.django_db
@pytest.mark.unit
class TestVITALsWidget:
    """Test VITAL lookup errors from the test import widget."""

    def test_missing_vital_error_identifies_imported_value(self, sample_module):
        """Identify the exact value that failed after an earlier successful lookup."""
        VITAL.objects.create(name="Existing VITAL", module=sample_module, VITAL_ID="1010_06")
        widget = VITALsWidget(VITAL, separator=";", field="VITAL_ID")

        with pytest.raises(VITAL.DoesNotExist, match=r"module code 'PHAS1234' and VITAL_ID '1030_12'"):
            widget.clean("PHAS1234:1010_06;PHAS1234:1030_12")

    def test_module_qualified_value_selects_vital(self, sample_module):
        """Resolve a VITAL from its module code and VITAL_ID."""
        vital = VITAL.objects.create(name="Existing VITAL", module=sample_module, VITAL_ID="1010_06")
        widget = VITALsWidget(VITAL, separator=";", field="VITAL_ID")

        assert widget.clean("PHAS1234:1010_06") == [vital]

    def test_unqualified_value_reports_expected_format(self):
        """Reject a VITAL_ID that does not include its module code."""
        widget = VITALsWidget(VITAL, separator=";", field="VITAL_ID")

        with pytest.raises(ValueError, match="MODULE_CODE:VITAL_ID format"):
            widget.clean("1010_06")

    def test_render_uses_module_qualified_values(self, sample_module):
        """Export VITALs in the same module-qualified format accepted by imports."""
        vital = VITAL.objects.create(name="Existing VITAL", module=sample_module, VITAL_ID="1010_06")
        widget = VITALsWidget(VITAL, separator=";", field="VITAL_ID")

        assert widget.render(VITAL.objects.filter(pk=vital.pk)) == "PHAS1234:1010_06"

    def test_vital_id_is_unique_within_module(self, sample_module):
        """Prevent duplicate VITAL_ID values within one module."""
        VITAL.objects.create(name="First VITAL", module=sample_module, VITAL_ID="1010_06")

        with pytest.raises(IntegrityError), transaction.atomic():
            VITAL.objects.create(name="Second VITAL", module=sample_module, VITAL_ID="1010_06")
