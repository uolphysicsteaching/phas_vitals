"""Import Export Admin Resources for the minerva app models."""

# external imports
from accounts.models import Account
from accounts.resource import AccountWidget
from import_export import fields, resources, widgets

# app imports
from .models import (
    Module,
    ModuleEnrollment,
    StatusCode,
    Test,
    Test_Attempt,
    Test_Score,
)

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
        widget=AccountWidget("accounts.Account", "display_name"),
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


class StatusCodeResource(resources.ModelResource):
    """Import-Export resource for Status Codes."""

    class Meta:
        model = StatusCode
        fields = ("code", "explanation", "capped", "valid", "resit", "level")
        import_id_fields = ["code"]


class ModuleEnrollmentReource(resources.ModelResource):
    """Import Export Resource for ModuleEnrollments."""

    class Meta:
        model = ModuleEnrollment
        fields = ("module", "student", "status")
        import_id_fields = ["module", "student"]

    student = fields.Field(
        column_name="student",
        attribute="student",
        widget=AccountWidget(Account, "display_name"),
    )

    module = fields.Field(
        column_name="module",
        attribute="module",
        widget=widgets.ForeignKeyWidget(Module, "code"),
    )

    status = fields.Field(
        column_name="status",
        attribute="status",
        widget=widgets.ForeignKeyWidget(StatusCode, "code"),
    )

    def import_row(self, row, instance_loader, using_transactions=True, dry_run=False, **kwargs):
        """Match up bad fields."""
        if "module" not in row and ("Subject_Code" in row and "Module_No" in row):
            row["module"] = row["Subject_Code"].strip() + str(row["Module_No"])
        if "student" not in row and "Student_ID" in row:
            row["student"] = row["Student_ID"]
        if "status" not in row and "RSTS_Code" in row:
            row["status"] = row["RSTS_Code"]
        return super().import_row(row, instance_loader, using_transactions=True, dry_run=False, **kwargs)
