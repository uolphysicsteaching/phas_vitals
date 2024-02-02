# Django imports
from django.contrib import admin

# external imports
from import_export import fields, resources, widgets
from import_export.admin import ImportExportMixin, ImportExportModelAdmin

# app imports
from .models import Module, Test, Test_Attempt, Test_Score

# Register your models here.


class ModuleResource(resources.ModelResource):

    """Import Export Resource for Module objects."""

    class Meta:
        model = Module
        fields = ("id", "uuid", "courseId", "name", "description", "programmes")
        import_id_fields = ["id"]

    programmes = fields.Field(
        column_name="programmes",
        attribute="programmes",
        widget=widgets.ManyToManyWidget("accounts.Programme", ";", "name"),
    )


class TestResource(resources.ModelResource):

    """Import Export Resource for Test objects."""

    class Meta:
        model = Test
        fields = (
            "test_id",
            "module",
            "name",
            "description",
            "externalGrade",
            "score_possible",
            "grading_due",
            "release_date",
            "recommended_date",
            "grading_attemptsAllowed",
        )
        import_id_fields = ["test_id"]

    module = fields.Field(
        column_name="module",
        attribute="module",
        widget=widgets.ForeignKeyWidget(Module, "id"),
    )


class Test_ScoreResource(resources.ModelResource):

    """Import Export Resource for Test_Score objects."""

    class Meta:
        model = Test_Attempt
        fields = (
            "user",
            "test",
            "status",
            "text",
            "score",
        )
        import_id_fields = ["id"]

    user = fields.Field(
        column_name="user",
        attribute="user",
        widget=widgets.ForeignKeyWidget("accounts.Account", "display_name"),
    )

    test = fields.Field(
        column_name="test",
        attribute="test",
        widget=widgets.ForeignKeyWidget(Test, "test_id"),
    )


class Test_AttemptResource(resources.ModelResource):

    """Import Export Resource for Test_Attempt objects."""

    class Meta:
        model = Test_Attempt
        fields = (
            "attempt_id",
            "test_entry",
            "status",
            "text",
            "score",
            "created",
            "attempted",
            "modified",
        )
        import_id_fields = ["attempt_id"]

    test_entry = fields.Field(
        column_name="test_entry",
        attribute="test_entry",
        widget=widgets.ForeignKeyWidget(Test_Score, "id"),
    )
