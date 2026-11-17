import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calls", "0003_call_recordings"),
        ("companies", "0003_platform_audit_log"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DjangoCallRecordingTranscriptModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(max_length=20)),
                ("transcript_text", models.TextField(blank=True, null=True)),
                ("segments", models.JSONField(default=list)),
                ("summary", models.TextField(blank=True, null=True)),
                ("key_points", models.JSONField(default=list)),
                ("action_items", models.JSONField(default=list)),
                ("language", models.CharField(blank=True, max_length=50, null=True)),
                ("model_name", models.CharField(blank=True, max_length=100, null=True)),
                ("error_message", models.CharField(blank=True, max_length=500, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("call", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="calls.djangocallmodel")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="companies.djangocompanymodel")),
                ("recording", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="transcript", to="calls.djangocallrecordingmodel")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "call_recording_transcripts",
            },
        ),
    ]
