import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    initial = True

    # Explicit dependency on the latest users migration so that users can later
    # depend on companies (users 0006) without creating a circular dependency.
    dependencies = [
        ("users", "0005_user_audit_log"),
    ]

    operations = [
        migrations.CreateModel(
            name="DjangoCompanyModel",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=100)),
                ("website", models.URLField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ONBOARDING", "Onboarding"),
                            ("ACTIVE", "Active"),
                            ("SUSPENDED", "Suspended"),
                        ],
                        db_index=True,
                        default="ONBOARDING",
                        max_length=20,
                    ),
                ),
                ("status_reason", models.TextField(blank=True)),
                ("status_changed_at", models.DateTimeField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "status_changed_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "companies",
                "ordering": ["name"],
                "constraints": [
                    models.UniqueConstraint(
                        Lower("slug"),
                        name="company_slug_lower_unique",
                    ),
                ],
            },
        ),
    ]
