import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0002_create_legacy_company"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformAuditLogModel",
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
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("COMPANY_CREATED", "Company created"),
                            ("COMPANY_UPDATED", "Company updated"),
                            ("COMPANY_SUSPENDED", "Company suspended"),
                            ("COMPANY_ACTIVATED", "Company activated"),
                            ("COMPANY_USER_CREATED", "Company user created"),
                            (
                                "COMPANY_USER_PASSWORD_RESET",
                                "Company user password reset",
                            ),
                            ("COMPANY_USER_BLOCKED", "Company user blocked"),
                            ("COMPANY_USER_UNBLOCKED", "Company user unblocked"),
                        ],
                        max_length=50,
                    ),
                ),
                ("actor_id", models.UUIDField()),
                ("actor_email", models.EmailField(max_length=254)),
                ("company_id", models.UUIDField(blank=True, null=True)),
                ("target_user_id", models.UUIDField(blank=True, null=True)),
                ("target_email", models.EmailField(blank=True, max_length=254)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "platform_audit_logs",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["company_id", "created_at"],
                        name="platform_audit_company_idx",
                    ),
                    models.Index(
                        fields=["action"],
                        name="platform_audit_action_idx",
                    ),
                ],
            },
        ),
    ]
