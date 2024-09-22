# Generated by Django 4.2.16 on 2024-09-16 15:43

# Django imports
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("minerva", "0008_alter_module_alt_code_alter_module_code_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="GradebookColumn",
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
                ("gradebook_id", models.CharField(max_length=255)),
                ("name", models.CharField(max_length=255, null=True)),
                (
                    "test",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cxolumns",
                        to="minerva.test",
                    ),
                ),
            ],
            options={
                "ordering": ["test__module__code", "test__name"],
            },
        ),
    ]