# Generated by Django 4.2.14 on 2024-08-07 21:58

# Django imports
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_alter_account_options"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="account",
            index=models.Index(fields=["number"], name="accounts_ac_number_92e5e2_idx"),
        ),
        migrations.AddIndex(
            model_name="account",
            index=models.Index(fields=["user_id"], name="accounts_ac_user_id_6d63db_idx"),
        ),
        migrations.AddIndex(
            model_name="account",
            index=models.Index(fields=["username"], name="accounts_ac_usernam_862e8e_idx"),
        ),
    ]
