# Generated by Django 4.2.9 on 2024-02-04 22:02

# Django imports
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vitals', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='vital_result',
            name='passed',
            field=models.BooleanField(default=False),
        ),
    ]