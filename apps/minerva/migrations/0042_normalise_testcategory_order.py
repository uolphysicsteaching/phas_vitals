# Django imports
from django.db import migrations


def normalise_testcategory_order(apps, schema_editor):
    """Give every existing test category a unique positive sort position."""
    TestCategory = apps.get_model("minerva", "TestCategory")
    categories = list(TestCategory.objects.using(schema_editor.connection.alias).order_by("order", "pk"))
    for order, category in enumerate(categories, start=1):
        category.order = order
    TestCategory.objects.using(schema_editor.connection.alias).bulk_update(categories, ["order"])


class Migration(migrations.Migration):

    dependencies = [
        ("minerva", "0041_moduleenrollment_locked"),
    ]

    operations = [
        migrations.RunPython(normalise_testcategory_order, migrations.RunPython.noop),
    ]
