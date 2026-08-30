# Generated manually for the meeting-template model transition.

# Django imports
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# external imports
import tinymce.models


def discard_test_meetings(apps, schema_editor):
    """Discard the old meeting data, which was used only for testing."""
    apps.get_model("tutorial", "Meeting").objects.all().delete()


class Migration(migrations.Migration):
    # PostgreSQL must commit discard_test_meetings() before fields can be
    # removed from tutorial_meeting; otherwise its deferred foreign-key
    # triggers remain pending and block the following ALTER TABLE statements.
    atomic = False

    dependencies = [
        ("accounts", "0033_school_account_school_programme_school_and_more"),
        ("tutorial", "0005_alter_attendance_id_alter_meeting_id_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(discard_test_meetings, migrations.RunPython.noop),
        migrations.RemoveField(model_name="meeting", name="students"),
        migrations.DeleteModel(name="MeetingAttendance"),
        migrations.RemoveField(model_name="meeting", name="due_date"),
        migrations.CreateModel(
            name="Question",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("yesno", "Yes/No"),
                            ("text", "Text"),
                            ("number", "Number"),
                            ("select", "Single choice"),
                            ("m-select", "Multiple choice"),
                        ],
                        max_length=8,
                    ),
                ),
                ("text", tinymce.models.HTMLField()),
                ("data", models.JSONField(blank=True, default=list)),
            ],
        ),
        migrations.AddField(
            model_name="meeting",
            name="due_semester",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, "Out of Semester"),
                    (1, "Semester 1"),
                    (2, "Semester 2"),
                    (3, "Semesters 1+2"),
                ],
                default=0,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="meeting",
            name="due_week",
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(name="meeting", options={"ordering": ("due_semester", "due_week", "name")}),
        migrations.AlterUniqueTogether(name="meeting", unique_together=set()),
        migrations.CreateModel(
            name="MeetingAttendance",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("in-person", "Attended in person"),
                            ("online", "Attended online"),
                            ("no-show", "Arranged but no show"),
                            ("no-contact", "No contact"),
                        ],
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "meeting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_records",
                        to="tutorial.meeting",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            ("groups__name", "Instructor"),
                            ("is_staff", True),
                            _connector="OR",
                        ),
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recorded_meetings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        limit_choices_to=models.Q(("groups__name", "Student")),
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="meeting_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="meetingattendance",
            constraint=models.UniqueConstraint(
                fields=("meeting", "student"),
                name="unique_meeting_student",
            ),
        ),
        migrations.RemoveField(
            model_name="meeting",
            name="cohort",
        ),
        migrations.AddField(
            model_name="meeting",
            name="level",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="meetings",
                to="accounts.year",
                verbose_name="Student level",
            ),
        ),
        migrations.AddConstraint(
            model_name="meeting",
            constraint=models.UniqueConstraint(fields=("name", "level"), name="unique_meeting_name_level"),
        ),
        migrations.AlterField(
            model_name="meeting",
            name="level",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="meetings",
                to="accounts.year",
                verbose_name="Student level",
            ),
        ),
        migrations.CreateModel(
            name="MeetingQuestion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("position", models.PositiveIntegerField()),
                (
                    "meeting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="question_links",
                        to="tutorial.meeting",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="meeting_links",
                        to="tutorial.question",
                    ),
                ),
            ],
            options={"ordering": ("meeting", "position")},
        ),
        migrations.AddConstraint(
            model_name="meetingquestion",
            constraint=models.UniqueConstraint(fields=("meeting", "question"), name="unique_question_per_meeting"),
        ),
        migrations.AddConstraint(
            model_name="meetingquestion",
            constraint=models.UniqueConstraint(
                fields=("meeting", "position"),
                name="unique_question_position_per_meeting",
            ),
        ),
        migrations.AddField(
            model_name="meeting",
            name="questions",
            field=models.ManyToManyField(
                blank=True,
                related_name="meetings",
                through="tutorial.MeetingQuestion",
                through_fields=("meeting", "question"),
                to="tutorial.question",
            ),
        ),
        migrations.CreateModel(
            name="Answer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("data", models.JSONField(default=dict)),
                (
                    "attendance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="tutorial.meetingattendance",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="answers",
                        to="tutorial.question",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="answer",
            constraint=models.UniqueConstraint(fields=("question", "attendance"), name="unique_answer_per_question"),
        ),
    ]
