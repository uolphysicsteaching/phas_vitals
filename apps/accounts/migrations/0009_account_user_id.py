# Generated by Django 4.2.11 on 2024-06-15 17:45

# Django imports
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_account_labs_score"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="user_id",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
