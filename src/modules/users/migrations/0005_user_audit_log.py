import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_user_deleted_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="DjangoUserAuditLogModel",
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
                ("action", models.CharField(db_index=True, max_length=50)),
                ("actor_id", models.UUIDField(db_index=True)),
                ("actor_email", models.EmailField(max_length=254)),
                ("target_user_id", models.UUIDField(db_index=True)),
                ("target_email", models.EmailField(max_length=254)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_index=True)),
            ],
            options={
                "db_table": "user_audit_logs",
                "ordering": ["-created_at"],
            },
        ),
    ]
