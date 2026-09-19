import uuid

from django.conf import settings
from django.db import models


class DjangoMeetingModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    is_all_day = models.BooleanField(
        default=False,
    )

    start_at = models.DateTimeField()

    end_at = models.DateTimeField()

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hosted_meetings",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_meetings",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    is_deleted = models.BooleanField(
        default=False,
    )

    class Meta:
        db_table = "meetings"
        indexes = [
            models.Index(fields=["is_deleted"]),
            models.Index(fields=["start_at"]),
            models.Index(fields=["end_at"]),
            models.Index(fields=["host"]),
        ]

    def __str__(self):
        return self.title
