# -*- coding: utf-8 -*-
"""Import Export Resource Classes for the vitals app."""
# Python imports
import logging

# Django imports
from django.apps import apps
from django.db.models import Q

# external imports
from import_export import fields, resources, widgets
from minerva.models import Module, Test

# app imports
from .models import VITAL, VITAL_Result, VITAL_Test_Map

logger = logging.getLogger(__name__)


class TestsWidget(widgets.ManyToManyWidget):
    """Import Export Widge for reading Tests that understands the natural key for a test."""

    def __init__(self, model, separator=None, field=None, **kwargs):
        """Handle converting model from string to model instance."""
        if isinstance(model, str):
            app, model = model.split(".")
            model = apps.get_model(app, model)
        super().__init__(model, separator, field, **kwargs)

    def clean(self, value, row=None, **kwargs):
        """Split the value by separator and then lookup natural keys."""
        if not isinstance(value, str):
            return self.model.objects.none()
        if self.separator in value:
            values = [x.strip() for x in value.split(self.separator) if x.strip() != ""]
        else:
            values = [value]
        ret = []
        for v in values:
            logger.debug(f"Looking for a test called {v}")
            ret.append(self.model.objects.get_by_natural_key(v))
        return ret

    def render(self, value, obj=None, **kwargs):
        """Render using natural keys."""
        if value is None:
            return ""
        ids = [str(obj) for obj in value.all()]
        return self.separator.join(ids)


class VITALResource(resources.ModelResource):
    """Import Export Resource for VITAL objects."""

    class Meta:
        model = VITAL
        fields = ("id", "name", "description", "module", "tests", "VITAL_ID")
        import_id_fields = ["id"]

    module = fields.Field(
        column_name="module",
        attribute="module",
        widget=widgets.ForeignKeyWidget(Module, "code"),
    )

    tests = fields.Field(column_name="tests", attribute="tests", widget=TestsWidget(Test, ";"))


class VITAL_ResultResource(resources.ModelResource):
    """Import Export Resource for VITAL_Results."""

    class Meta:
        model = VITAL_Result
        fields = ("id", "vital", "user", "date_passed")
        import_id_fields = ["id"]

    vital = fields.Field(
        column_name="vital",
        attribute="vital",
        widget=widgets.ForeignKeyWidget(VITAL, use_natural_foreign_keys=True),
    )

    user = fields.Field(
        column_name="user",
        attribute="user",
        widget=widgets.ForeignKeyWidget("accounts.Account", "display_name"),
    )


class VITAL_Test_MapResource(resources.ModelResource):
    """Import Export Resource for  VITAL_Test_Mappings."""

    class Meta:
        model = VITAL_Test_Map
        fields = ("id", "test", "vital", "necessary", "sufficient")
        import_id_fields = ["id"]

    vital = fields.Field(
        column_name="vital",
        attribute="vital",
        widget=widgets.ForeignKeyWidget(VITAL, use_natural_foreign_keys=True),
    )

    test = fields.Field(
        column_name="test",
        attribute="test",
        widget=widgets.ForeignKeyWidget("minerva.Test", "name"),
    )
