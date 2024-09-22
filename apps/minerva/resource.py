"""Import Export Admin Resources for the minerva app models."""

# external imports
import numpy as np
from accounts.models import Account
from accounts.resource import AccountsWidget, AccountWidget, ProgrammesWidget
from import_export import fields, resources, widgets

# app imports
from .models import (
    GradebookColumn,
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
        fields = (
            "id",
            "uuid",
            "courseId",
            "year",
            "semester",
            "level",
            "exam_code",
            "code",
            "name",
            "description",
            "module_leader",
            "team_members",
        )
        import_id_fields = ["id"]

    module_leader = fields.Field(
        column_name="module_leader",
        attribute="module_leader",
        widget=AccountWidget("accounts.Account", "display_name"),
    )
    team_members = fields.Field(
        column_name="team_members",
        attribute="team_members",
        widget=AccountsWidget("accounts.Account", ";", "display_name"),
    )


class TestResource(resources.ModelResource):
    """Import Export Resource for Test objects."""

    class Meta:
        model = Test
        fields = (
            "test_id",
            "module",
            "name",
            "type",
            "description",
            "externalGrade",
            "score_possible",
            "passing_score",
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

    def before_import_row(self, row, row_number=None, **kwargs):
        super().before_import_row(row, row_number=row_number, **kwargs)
        if not row["test_id"]:
            row["test_id"] = f"_{np.random.randint(1E6)}_X"


class GradebookColumnResource(resources.ModelResource):
    """Import-Export resource for Gradebook columns."""

    class Meta:
        model = GradebookColumn
        fields = ("gradebook_id", "name", "test")
        import_id_fields = ["gradebook_id"]

    test = fields.Field(
        column_name="test",
        attribute="test",
        widget=widgets.ForeignKeyWidget(Test, "test_id"),
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
