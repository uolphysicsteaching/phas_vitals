# -*- coding: utf-8 -*-
"""Import Export Resource Classes for the vitals app."""

# external imports
from import_export import fields, resources, widgets

# app imports
from .models import VITAL, VITAL_Result, VITAL_Test_Map


class VITALResource(resources.ModelResource):

    """Import Export Resource for VITAL objects."""

    class Meta:
        model = VITAL
        fields = ("id", "name", "description", "module", "tests")
        import_id_fields = ["id"]

    module = fields.Field(
        column_name="module",
        attribute="module",
        widget=widgets.ForeignKeyWidget("minerva.Module", "name"),
    )

    tests = fields.Field(
        column_name="tests", attribute="tests", widget=widgets.ManyToManyWidget("minerva.Test", ";", "test_id")
    )


class VITAL_ResultResource(resources.ModelResource):

    """Import Export Resource for VITAL_Results."""

    class Meta:
        model = VITAL_Result
        fields = ("id", "vital", "user", "date_passed")
        import_id_fields = ["id"]

    vital = fields.Field(
        column_name="vital",
        attribute="vital",
        widget=widgets.ForeignKeyWidget(VITAL, "name"),
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
        widget=widgets.ForeignKeyWidget(VITAL, "name"),
    )

    test = fields.Field(
        column_name="test",
        attribute="test",
        widget=widgets.ForeignKeyWidget("minerva.Test", "name"),
    )
