# Generated by Django 4.2.10 on 2024-03-04 22:04

# Django imports
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_account_apt"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="account",
            name="apt",
        ),
    ]
