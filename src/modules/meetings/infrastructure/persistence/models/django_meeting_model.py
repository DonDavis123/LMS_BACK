import uuid

from django.conf import settings
from django.db import models

from src.modules.meetings.domain.enums.conference_provider import ConferenceProvider
from src.modules.meetings.domain.enums.conference_status import ConferenceStatus


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

    reminder_at = models.DateTimeField(
        blank=True,
        null=True,
    )

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

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    meet_link = models.URLField(
        max_length=500,
        blank=True,
        null=True,
    )

    external_event_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    conference_provider = models.CharField(
        max_length=32,
        choices=[(item.value, item.value) for item in ConferenceProvider],
        blank=True,
        null=True,
    )

    conference_status = models.CharField(
        max_length=16,
        choices=[(item.value, item.value) for item in ConferenceStatus],
        default=ConferenceStatus.NONE.value,
    )

    conference_error = models.TextField(
        blank=True,
        null=True,
    )

    # User whose (Google) calendar holds the external event.
    calendar_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
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
