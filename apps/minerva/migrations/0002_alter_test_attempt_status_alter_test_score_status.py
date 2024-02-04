# Generated by Django 4.2.3 on 2024-02-02 10:39

# Django imports
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("minerva", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="test_attempt",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NotAttempted", "None of the students in a group has submitted an attempt"),
                    ("InProgress", "Attempt activity has commenced, but has not been submitted for grading"),
                    ("NeedsGrading", "Attempt has been submitted for grading, but has not been fully graded"),
                    ("Completed", "A grade has been entered for the attempt"),
                    ("InProgressAgain", "New student activity occurred after the grade was entered"),
                    ("NeedsGradingAgain", "New Student activity needs grade ipdating"),
                ],
                max_length=40,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="test_score",
            name="status",
            field=models.CharField(
                choices=[("Graded", "Score Graded"), ("NeedsGrading", "Not Marked Yet")], max_length=50
            ),
        ),
    ]
