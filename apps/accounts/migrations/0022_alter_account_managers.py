# Generated by Django 4.2.16 on 2024-10-10 11:39

# Django imports
import django.contrib.auth.models
import django.db.models.manager
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0021_account_givenname"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="account",
            managers=[
                ("students", django.db.models.manager.Manager()),
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
    ]
