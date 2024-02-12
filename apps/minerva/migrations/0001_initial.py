# Generated by Django 4.2.3 on 2024-02-11 22:07

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import minerva.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Module",
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
                ("uuid", models.CharField(max_length=32)),
                ("courseId", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "code",
                    models.CharField(
                        max_length=11, validators=[minerva.models.module_validator]
                    ),
                ),
                ("alt_code", models.CharField(blank=True, max_length=11, null=True)),
                ("credits", models.IntegerField(default=0)),
                ("name", models.CharField(max_length=80)),
                ("level", models.IntegerField(blank=True, null=True)),
                ("semester", models.IntegerField(blank=True, null=True)),
                ("exam_code", models.IntegerField(default=1)),
                ("description", models.TextField(blank=True, null=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "module_leader",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="_modules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("code", "exam_code"),
            },
        ),
        migrations.CreateModel(
            name="StatusCode",
            fields=[
                (
                    "code",
                    models.CharField(max_length=2, primary_key=True, serialize=False),
                ),
                (
                    "explanation",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                ("capped", models.BooleanField(default=False)),
                ("valid", models.BooleanField(default=True)),
                ("resit", models.BooleanField(default=False)),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("normal", "Normal first attempt"),
                            ("first", "First Attempt Resit"),
                            ("second", "Second or further Resit"),
                            ("none", "Not an Attempt"),
                        ],
                        default="none",
                        max_length=10,
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
                    models.FloatField(
                        default=100, verbose_name="Maximum possible score"
                    ),
                ),
                (
                    "passing_score",
                    models.FloatField(
                        default=80, verbose_name="Maximum possible score"
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
                        blank=True,
                        choices=[
                            ("Graded", "Score Graded"),
                            ("NeedsGrading", "Not Marked Yet"),
                        ],
                        max_length=50,
                        null=True,
                    ),
                ),
                ("text", models.TextField(blank=True, null=True)),
                ("score", models.FloatField(blank=True, null=True)),
                ("passed", models.BooleanField(default=False)),
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
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("attempt_id", models.CharField(max_length=255, unique=True)),
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
                        max_length=40,
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
        migrations.CreateModel(
            name="ModuleEnrollment",
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
                    "module",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_enrollments",
                        to="minerva.module",
                    ),
                ),
                (
                    "status",
                    models.ForeignKey(
                        default="RE",
                        on_delete=django.db.models.deletion.SET_DEFAULT,
                        to="minerva.statuscode",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="module_enrollments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="module",
            name="students",
            field=models.ManyToManyField(
                related_name="modules",
                through="minerva.ModuleEnrollment",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="module",
            name="team_members",
            field=models.ManyToManyField(
                blank=True, related_name="_module_teams", to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name="module",
            name="updater",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="test_score",
            constraint=models.UniqueConstraint(
                fields=("test", "user"), name="Singleton mapping student and test_score"
            ),
        ),
        migrations.AddConstraint(
            model_name="test",
            constraint=models.UniqueConstraint(
                fields=("module", "name"), name="Singleton name of a test per module"
            ),
        ),
        migrations.AddConstraint(
            model_name="moduleenrollment",
            constraint=models.UniqueConstraint(
                fields=("module", "student"), name="Singleton EWnrollment on a module"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="module",
            unique_together={("code", "exam_code")},
        ),
    ]
