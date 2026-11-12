import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calls", "0002_call_status"),
        ("companies", "0003_platform_audit_log"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DjangoCallRecordingModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("file_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=100)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("storage_key", models.CharField(max_length=500, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("call", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recordings", to="calls.djangocallmodel")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="companies.djangocompanymodel")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "call_recordings",
                "indexes": [
                    models.Index(fields=["company", "call", "-created_at"], name="call_rec_co_call_created_idx"),
                ],
            },
        ),
    ]
