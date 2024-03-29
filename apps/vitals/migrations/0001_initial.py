# Generated by Django 4.2.3 on 2024-02-11 22:07

# Django imports
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("minerva", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VITAL",
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
                ("name", models.CharField(blank=True, max_length=255, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "module",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="VITALS",
                        to="minerva.module",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="VITAL_Test_Map",
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
                ("necessary", models.BooleanField(default=False)),
                ("sufficient", models.BooleanField(default=True)),
                (
                    "test",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vitals_mappings",
                        to="minerva.test",
                    ),
                ),
                (
                    "vital",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tests_mappings",
                        to="vitals.vital",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="VITAL_Result",
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
                ("passed", models.BooleanField(default=False)),
                (
                    "date_passed",
                    models.DateTimeField(blank=True, null=True, verbose_name="Date Achieved"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vital_results",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "vital",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_results",
                        to="vitals.vital",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="vital",
            name="students",
            field=models.ManyToManyField(
                related_name="VITALS",
                through="vitals.VITAL_Result",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="vital",
            name="tests",
            field=models.ManyToManyField(
                related_name="VITALS",
                through="vitals.VITAL_Test_Map",
                to="minerva.test",
            ),
        ),
        migrations.AddConstraint(
            model_name="vital_result",
            constraint=models.UniqueConstraint(fields=("vital", "user"), name="Singleton mapping student and vital"),
        ),
        migrations.AddConstraint(
            model_name="vital",
            constraint=models.UniqueConstraint(fields=("name", "module"), name="Singleton VITAL name per module"),
        ),
    ]
