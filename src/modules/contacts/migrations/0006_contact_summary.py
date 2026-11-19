import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0003_platform_audit_log"),
        ("contacts", "0005_backfill_contact_company"),
    ]

    operations = [
        migrations.CreateModel(
            name="DjangoContactSummaryModel",
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
                ("contact", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="contacts.djangocontactmodel")),
            ],
            options={
                "db_table": "contact_summaries",
            },
        ),
    ]
