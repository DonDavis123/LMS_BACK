from datetime import datetime
from uuid import UUID

from src.modules.reminders.application.interfaces.reminder_repository import (
    ReminderRepository,
)
from src.modules.reminders.domain.entities.reminder import Reminder

from .models import DjangoReminderModel


class DjangoReminderRepository(ReminderRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoReminderModel.objects.filter(company_id=self._company_id)

    def save(self, reminder: Reminder) -> Reminder:
        if reminder.task_id is not None and reminder.meeting_id is not None:
            raise ValueError(
                "A Reminder cannot be associated with both a Task and a Meeting."
            )

        model, _ = self._base_queryset().update_or_create(
            id=reminder.id,
            defaults={
                "company_id": self._company_id,
                "subject": reminder.subject,
                "remind_at": reminder.remind_at,
                "user_id": reminder.user_id,
                "task_id": reminder.task_id,
                "meeting_id": reminder.meeting_id,
                "is_enabled": reminder.is_enabled,
            },
        )
        return self._to_domain(model)

    def get_by_id(self, reminder_id: UUID) -> Reminder | None:
        try:
            model = self._base_queryset().get(id=reminder_id)
        except DjangoReminderModel.DoesNotExist:
            return None
        return self._to_domain(model)

    def get_by_user(self, user_id: UUID) -> list[Reminder]:
        models = self._base_queryset().filter(
            user_id=user_id,
        ).order_by("remind_at", "id")
        return [self._to_domain(model) for model in models]

    def get_by_task(self, task_id: UUID) -> list[Reminder]:
        models = self._base_queryset().filter(
            task_id=task_id,
        ).order_by("remind_at", "id")
        return [self._to_domain(model) for model in models]

    def get_by_meeting(self, meeting_id: UUID) -> list[Reminder]:
        models = self._base_queryset().filter(
            meeting_id=meeting_id,
        ).order_by("remind_at", "id")
        return [self._to_domain(model) for model in models]

    def get_due(self, as_of: datetime) -> list[Reminder]:
        models = self._base_queryset().filter(
            remind_at__lte=as_of,
            is_enabled=True,
        ).order_by("remind_at", "id")
        return [self._to_domain(model) for model in models]

    def delete_by_id(self, reminder_id: UUID) -> bool:
        deleted, _ = self._base_queryset().filter(id=reminder_id).delete()
        return deleted > 0

    def count_by_user_id(self, user_id: UUID) -> int:
        return self._base_queryset().filter(user_id=user_id).count()

    def delete_by_user_id(self, user_id: UUID) -> int:
        deleted, _ = self._base_queryset().filter(user_id=user_id).delete()
        return deleted

    @staticmethod
    def _to_domain(model: DjangoReminderModel) -> Reminder:
        return Reminder(
            id=model.id,
            subject=model.subject,
            remind_at=model.remind_at,
            user_id=model.user_id,
            task_id=model.task_id,
            meeting_id=model.meeting_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_enabled=model.is_enabled,
        )
