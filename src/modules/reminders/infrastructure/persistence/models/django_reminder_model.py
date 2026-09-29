import uuid

from django.conf import settings
from django.db import models

from src.modules.meetings.infrastructure.persistence.models.django_meeting_model import (
    DjangoMeetingModel,
)
from src.modules.tasks.infrastructure.persistence.models.django_task_model import (
    DjangoTaskModel,
)


class DjangoReminderModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    subject = models.CharField(
        max_length=255,
    )

    remind_at = models.DateTimeField()

    is_enabled = models.BooleanField(
        default=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reminders",
    )

    task = models.ForeignKey(
        DjangoTaskModel,
        on_delete=models.CASCADE,
        related_name="reminders",
        blank=True,
        null=True,
    )

    meeting = models.ForeignKey(
        DjangoMeetingModel,
        on_delete=models.CASCADE,
        related_name="reminders",
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
        db_table = "reminders"
        indexes = [
    models.Index(
        fields=["user", "remind_at"],
        name="reminders_user_id_1c0e7f_idx",
    ),
    models.Index(
        fields=["remind_at"],
        name="reminders_remind_8eeb0a_idx",
    ),
    models.Index(
        fields=["task"],
        name="reminders_task_id_6d6f2f_idx",
    ),
    models.Index(
        fields=["meeting"],
        name="reminders_meetin_1d5a4b_idx",
    ),
]
        constraints = [
    models.CheckConstraint(
        condition=models.Q(meeting__isnull=True) | models.Q(task__isnull=True),
        name="reminder_single_target",
    ),
]

    def __str__(self):
        return self.subject
