# Generated by Django 4.2.19 on 2025-02-18 09:43

# Django imports
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("minerva", "0012_test_ignore_zero"),
        ("vitals", "0003_alter_vital_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vital",
            name="module",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="VITALS",
                to="minerva.module",
            ),
        ),
    ]
