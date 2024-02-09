# Generated by Django 4.2.3 on 2024-02-09 20:07

# Django imports
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('minerva', '0006_alter_module_id'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='test',
            constraint=models.UniqueConstraint(fields=('module', 'name'), name='Singleton name of a test per module'),
        ),
    ]
