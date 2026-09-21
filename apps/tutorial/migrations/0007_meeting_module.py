# Generated manually to preserve existing meeting templates.

# Django imports
import django.db.models.deletion
from django.db import migrations, models


def assign_existing_meetings_to_phas1000(apps, schema_editor):
    """Assign existing meeting templates to the standard tutorial module."""
    Meeting = apps.get_model("tutorial", "Meeting")
    if not Meeting.objects.exists():
        return

    Module = apps.get_model("minerva", "Module")
    try:
        module = Module.objects.get(code="PHAS1000", exam_code=1)
    except Module.DoesNotExist as error:
        raise RuntimeError("Cannot migrate meetings because the PHAS1000 module does not exist.") from error
    Meeting.objects.update(module_id=module.pk)


class Migration(migrations.Migration):
    # Commit the data update before removing the old foreign key. PostgreSQL
    # otherwise retains deferred trigger events that can block the ALTER TABLE.
    atomic = False

    dependencies = [
        ("minerva", "0040_test_locked"),
        ("tutorial", "0006_replace_meeting_test_data_with_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="meeting",
            name="module",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="meetings",
                to="minerva.module",
                verbose_name="Module code",
            ),
        ),
        migrations.RunPython(assign_existing_meetings_to_phas1000, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="meeting",
            name="unique_meeting_name_level",
        ),
        migrations.RemoveField(
            model_name="meeting",
            name="level",
        ),
        migrations.AlterField(
            model_name="meeting",
            name="module",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="meetings",
                to="minerva.module",
                verbose_name="Module code",
            ),
        ),
        migrations.AddConstraint(
            model_name="meeting",
            constraint=models.UniqueConstraint(fields=("name", "module"), name="unique_meeting_name_module"),
        ),
    ]
