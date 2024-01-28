# Generated by Django 4.2.3 on 2024-01-28 17:31

from django.conf import settings
import django.contrib.auth.models
import django.contrib.auth.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cohort",
            fields=[
                (
                    "name",
                    models.CharField(max_length=20, primary_key=True, serialize=False),
                ),
            ],
            options={
                "ordering": ["-name"],
            },
        ),
        migrations.CreateModel(
            name="Programme",
            fields=[
                ("name", models.CharField(default="Unknown", max_length=150)),
                (
                    "code",
                    models.CharField(max_length=15, primary_key=True, serialize=False),
                ),
                (
                    "local",
                    models.BooleanField(
                        default=False, verbose_name="Parented by school"
                    ),
                ),
                (
                    "level",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("B", "Bachelors"),
                            ("MB", "Integrated Masters"),
                            ("PGT", "Taught Masters"),
                            ("O", "Other"),
                        ],
                        max_length=10,
                        null=True,
                        verbose_name="Degree Level",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Account",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        unique=True,
                        validators=[
                            django.contrib.auth.validators.UnicodeUsernameValidator()
                        ],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, verbose_name="email address"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                ("number", models.IntegerField(blank=True, null=True)),
                ("title", models.CharField(blank=True, max_length=20, null=True)),
                (
                    "programme",
                    models.CharField(blank=True, default="", max_length=50, null=True),
                ),
                (
                    "level",
                    models.IntegerField(
                        choices=[
                            (-1, "Not a student"),
                            (0, "Foundation Year"),
                            (1, "First Year"),
                            (2, "Second Year"),
                            (3, "Third Yea"),
                            (4, "Placement"),
                            (5, "Masters"),
                        ],
                        default=1,
                        verbose_name="Current Level of Study",
                    ),
                ),
                (
                    "registration_status",
                    models.CharField(blank=True, default="", max_length=10, null=True),
                ),
                (
                    "apt",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to=models.Q(
                            ("groups__name", "Grader"),
                            ("groups__name", "Teaching Assistant"),
                            _connector="OR",
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tutees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "cohort",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="students",
                        to="accounts.cohort",
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "ordering": ["last_name", "first_name"],
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
    ]
