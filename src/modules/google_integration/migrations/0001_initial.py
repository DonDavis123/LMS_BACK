import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("companies", "0003_platform_audit_log"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DjangoGoogleConnectionModel",
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
                ("google_email", models.EmailField(max_length=254)),
                ("refresh_token_encrypted", models.TextField()),
                ("scopes", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[("connected", "connected"), ("revoked", "revoked")],
                        default="connected",
                        max_length=16,
                    ),
                ),
                ("connected_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="companies.djangocompanymodel",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="google_connection",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "google_connections",
            },
        ),
    ]
