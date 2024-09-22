# Generated by Django 4.2.15 on 2024-08-26 17:38

# Django imports
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("util", "0002_groupedtreeitem_access_staff_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="groupedtreeitem",
            name="groups",
            field=models.ManyToManyField(
                blank=True,
                null=True,
                related_name="allowed_menu_items",
                to="auth.group",
                verbose_name="Access Groups",
            ),
        ),
        migrations.AlterField(
            model_name="groupedtreeitem",
            name="not_groups",
            field=models.ManyToManyField(
                blank=True,
                null=True,
                related_name="blocked_menu_items",
                to="auth.group",
                verbose_name="Blocked Groups",
            ),
        ),
    ]