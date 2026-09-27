import uuid

from django.conf import settings
from django.db import models

from src.modules.meetings.infrastructure.persistence.models.django_meeting_model import (
    DjangoMeetingModel,
)
from src.modules.reminders.infrastructure.persistence.models.django_reminder_model import (
    DjangoReminderModel,
)
from src.modules.tasks.infrastructure.persistence.models.django_task_model import (
    DjangoTaskModel,
)

from src.modules.notifications.domain.enums.notification_type import NotificationType


class DjangoNotificationModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    notification_type = models.CharField(
        max_length=30,
        choices=[
            (notification_type.value, notification_type.value)
            for notification_type in NotificationType
        ],
    )

    title = models.CharField(
        max_length=255,
    )

    message = models.TextField()

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notifications",
    )

    task = models.ForeignKey(
        DjangoTaskModel,
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )

    meeting = models.ForeignKey(
        DjangoMeetingModel,
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )

    reminder = models.ForeignKey(
        DjangoReminderModel,
        on_delete=models.SET_NULL,
        related_name="notifications",
        blank=True,
        null=True,
    )

    scheduled_for = models.DateTimeField()

    expires_at = models.DateTimeField()

    is_read = models.BooleanField(
        default=False,
    )

    read_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "notifications"
        indexes = [
            models.Index(fields=["user", "scheduled_for"]),
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["scheduled_for"]),
            models.Index(fields=["task"]),
            models.Index(fields=["meeting"]),
            models.Index(fields=["reminder"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(task__isnull=True)
                    | models.Q(meeting__isnull=True)
                ),
                name="notification_single_target",
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(is_read=False) & models.Q(read_at__isnull=True))
                    | (models.Q(is_read=True) & models.Q(read_at__isnull=False))
                ),
                name="notification_read_state_match",
            ),
        ]

    def __str__(self):
        return self.title
