# Generated manually for the Timeline feature.
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("leads", "0003_djangoleadmodel_is_converted_and_more"),
        ("contacts", "0003_djangocontactmodel_is_deleted"),
        ("accounts", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="TimelineEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=80)),
                ("message", models.CharField(max_length=500)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timeline_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "timeline_events"},
        ),
        migrations.CreateModel(
            name="TimelineEventTarget",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("entity_type", models.CharField(max_length=20)),
                ("entity_id", models.UUIDField()),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="targets", to="timeline.timelineevent")),
            ],
            options={"db_table": "timeline_event_targets"},
        ),
        migrations.AddConstraint(
            model_name="timelineeventtarget",
            constraint=models.UniqueConstraint(fields=("event", "entity_type", "entity_id"), name="timeline_event_target_unique"),
        ),
        migrations.AddIndex(
            model_name="timelineevent",
            index=models.Index(fields=["created_at"], name="timeline_event_created_idx"),
        ),
        migrations.AddIndex(
            model_name="timelineeventtarget",
            index=models.Index(fields=["entity_type", "entity_id"], name="timeline_target_entity_idx"),
        ),
    ]
