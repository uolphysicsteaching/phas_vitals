# Generated by Django 4.2.10 on 2024-03-03 22:02

# Django imports
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# external imports
import tinymce.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0002_alter_account_apt"),
    ]

    operations = [
        migrations.CreateModel(
            name="Meeting",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=40)),
                ("notes", tinymce.models.HTMLField(blank=True, default="")),
                ("due_date", models.DateField(blank=True, null=True)),
                (
                    "cohort",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="meetings",
                        to="accounts.cohort",
                        verbose_name="Student cohort",
                    ),
                ),
            ],
            options={
                "ordering": ("due_date",),
            },
        ),
        migrations.CreateModel(
            name="SessionType",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=30, unique=True)),
                (
                    "description",
                    models.CharField(blank=True, max_length=120, null=True),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Tutorial",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(max_length=20, unique=True)),
                (
                    "cohort",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tutorial_groups",
                        to="accounts.cohort",
                        verbose_name="Student cohort",
                    ),
                ),
            ],
            options={
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="TutorialAssignment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "integrity_test",
                    models.BooleanField(default=False, verbose_name="Academic Integrity Test"),
                ),
                (
                    "pebblepad_form",
                    models.BooleanField(default=False, verbose_name="Pebblepad Workbook"),
                ),
                (
                    "student",
                    models.OneToOneField(
                        limit_choices_to=models.Q(("groups__name", "Student")),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tutorial_group_assignment",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tutorial",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tutees",
                        to="tutorial.tutorial",
                    ),
                ),
            ],
            options={
                "unique_together": {("tutorial", "student")},
            },
        ),
        migrations.AddField(
            model_name="tutorial",
            name="students",
            field=models.ManyToManyField(
                related_name="tutorial_group",
                through="tutorial.TutorialAssignment",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="tutorial",
            name="tutor",
            field=models.ForeignKey(
                limit_choices_to=models.Q(("groups__name", "Instructor"), ("is_staff", True), _connector="OR"),
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tutor_groups",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Tutor",
            ),
        ),
        migrations.CreateModel(
            name="Session",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=30)),
                (
                    "semester",
                    models.IntegerField(
                        choices=[
                            (0, "Out of Semester"),
                            (1, "Semester 1"),
                            (2, "Semester 2"),
                            (3, "Semesters 1+2"),
                        ],
                        default=0,
                    ),
                ),
                ("week", models.IntegerField(default=0)),
                ("start", models.DateField()),
                ("end", models.DateField()),
                (
                    "cohort",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to="accounts.cohort",
                    ),
                ),
            ],
            options={
                "ordering": ("start",),
                "unique_together": {("name", "semester", "cohort")},
            },
        ),
        migrations.CreateModel(
            name="MeetingAttendance",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("submitted", models.DateTimeField(auto_now=True)),
                (
                    "meeting",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_records",
                        to="tutorial.meeting",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        limit_choices_to=models.Q(("groups__name", "Student")),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="meeting_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tutor",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            ("groups__name", "Instructor"),
                            ("is_staff", True),
                            _connector="OR",
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tutorial_meetings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("meeting", "student")},
            },
        ),
        migrations.AddField(
            model_name="meeting",
            name="students",
            field=models.ManyToManyField(
                related_name="meetings",
                through="tutorial.MeetingAttendance",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="meeting",
            unique_together={("name", "cohort")},
        ),
        migrations.CreateModel(
            name="Attendance",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "score",
                    models.FloatField(
                        blank=True,
                        choices=[
                            (-1.0, "Allowed Absence"),
                            (0.0, "Unexplained Absence"),
                            (1.0, "Present limited engagement"),
                            (2.0, "Present, good engagement"),
                            (3.0, "Present, outstanding engagement"),
                        ],
                        null=True,
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attended_by",
                        to="tutorial.session",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        limit_choices_to=models.Q(("groups__name", "Student")),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "type",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attended_by",
                        to="tutorial.sessiontype",
                    ),
                ),
            ],
            options={
                "ordering": ("student", "session"),
                "unique_together": {("student", "session", "type")},
            },
        ),
    ]
