import uuid

from django.db import models

from .timeline_event import TimelineEvent


class TimelineEventTarget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        TimelineEvent,
        on_delete=models.CASCADE,
        related_name="targets",
    )
    entity_type = models.CharField(max_length=20)
    entity_id = models.UUIDField()
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "timeline_event_targets"
        constraints = [
            models.UniqueConstraint(
                fields=["event", "entity_type", "entity_id"],
                name="timeline_event_target_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"], name="timeline_target_entity_idx"),
        ]
