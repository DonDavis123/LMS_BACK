import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0003_platform_audit_log"),
        ("leads", "0010_lead_import_job"),
    ]

    operations = [
        migrations.CreateModel(
            name="DjangoLeadSummaryModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("headline", models.TextField()),
                ("key_points", models.JSONField(default=list)),
                ("next_steps", models.JSONField(default=list)),
                ("model_name", models.CharField(blank=True, max_length=100, null=True)),
                ("timeline_events_used", models.PositiveIntegerField(default=0)),
                ("calls_used", models.PositiveIntegerField(default=0)),
                ("generated_at", models.DateTimeField()),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="companies.djangocompanymodel")),
                ("lead", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="leads.djangoleadmodel")),
            ],
            options={
                "db_table": "lead_summaries",
            },
        ),
    ]
