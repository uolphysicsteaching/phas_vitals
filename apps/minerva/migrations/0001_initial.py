# Generated by Django 4.2.9 on 2024-01-30 21:58

# Django imports
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0003_alter_account_programme"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Module",
            fields=[
                (
                    "id",
                    models.CharField(max_length=255, primary_key=True, serialize=False),
                ),
                ("uuid", models.CharField(max_length=32)),
                ("courseId", models.CharField(blank=True, max_length=255, null=True)),
                ("name", models.CharField(blank=True, max_length=255, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "programmes",
                    models.ManyToManyField(
                        related_name="modules", to="accounts.programme"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Test",
            fields=[
                (
                    "test_id",
                    models.CharField(max_length=255, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "externalGrade",
                    models.BooleanField(default=True, verbose_name="Grade from LTI"),
                ),
                (
                    "score_possible",
                    models.IntegerField(
                        default=100, verbose_name="Maximum possible score"
                    ),
                ),
                (
                    "grading_due",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Minerva Due Date"
                    ),
                ),
                (
                    "release_date",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Test Available Date"
                    ),
                ),
                (
                    "recommended_date",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Recomemnded Attempt Date"
                    ),
                ),
                (
                    "grading_attemptsAllowed",
                    models.IntegerField(
                        blank=True, null=True, verbose_name="Number of allowed attempts"
                    ),
                ),
                (
                    "module",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tests",
                        to="minerva.module",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Test_Score",
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
                            ("Graded", "Score Graded"),
                            ("NeedsGrading", "Not Marked Yet"),
                        ]
                    ),
                ),
                ("text", models.TextField(blank=True, null=True)),
                ("score", models.FloatField(blank=True, null=True)),
                (
                    "test",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="minerva.test",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="test_results",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Test_Attempt",
            fields=[
                (
                    "attempt_id",
                    models.CharField(max_length=255, primary_key=True, serialize=False),
                ),
                (
                    "status",
                    models.CharField(
                        blank=True,
                        choices=[
                            (
                                "NotAttempted",
                                "None of the students in a group has submitted an attempt",
                            ),
                            (
                                "InProgress",
                                "Attempt activity has commenced, but has not been submitted for grading",
                            ),
                            (
                                "NeedsGrading",
                                "Attempt has been submitted for grading, but has not been fully graded",
                            ),
                            ("Completed", "A grade has been entered for the attempt"),
                            (
                                "InProgressAgain",
                                "New student activity occurred after the grade was entered",
                            ),
                            (
                                "NeedsGradingAgain",
                                "New Student activity needs grade ipdating",
                            ),
                        ],
                        null=True,
                    ),
                ),
                ("text", models.TextField(blank=True, null=True)),
                ("score", models.FloatField(blank=True, null=True)),
                ("created", models.DateTimeField(blank=True, null=True)),
                ("attempted", models.DateTimeField(blank=True, null=True)),
                ("modified", models.DateTimeField(blank=True, null=True)),
                (
                    "test_entry",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="minerva.test_score",
                    ),
                ),
            ],
        ),
    ]