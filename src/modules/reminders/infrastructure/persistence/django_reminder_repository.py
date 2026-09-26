from datetime import datetime
from uuid import UUID

from src.modules.reminders.application.interfaces.reminder_repository import (
    ReminderRepository,
)
from src.modules.reminders.domain.entities.reminder import Reminder

from .models import DjangoReminderModel


class DjangoReminderRepository(ReminderRepository):

    def save(self, reminder: Reminder) -> Reminder:
        if reminder.task_id is not None and reminder.meeting_id is not None:
            raise ValueError(
                "A Reminder cannot be associated with both a Task and a Meeting."
            )

        model, _ = DjangoReminderModel.objects.update_or_create(
            id=reminder.id,
            defaults={
                "subject": reminder.subject,
                "remind_at": reminder.remind_at,
                "user_id": reminder.user_id,
                "task_id": reminder.task_id,
                "meeting_id": reminder.meeting_id,
            },
        )
        return self._to_domain(model)

    def get_by_id(self, reminder_id: UUID) -> Reminder | None:
        try:
            model = DjangoReminderModel.objects.get(id=reminder_id)
        except DjangoReminderModel.DoesNotExist:
            return None
        return self._to_domain(model)

    def get_by_user(self, user_id: UUID) -> list[Reminder]:
        models = DjangoReminderModel.objects.filter(
            user_id=user_id,
        ).order_by("remind_at", "id")
        return [self._to_domain(model) for model in models]

    def get_by_task(self, task_id: UUID) -> list[Reminder]:
        models = DjangoReminderModel.objects.filter(
            task_id=task_id,
        ).order_by("remind_at", "id")
        return [self._to_domain(model) for model in models]

    def get_by_meeting(self, meeting_id: UUID) -> list[Reminder]:
        models = DjangoReminderModel.objects.filter(
            meeting_id=meeting_id,
        ).order_by("remind_at", "id")
        return [self._to_domain(model) for model in models]

    def get_due(self, as_of: datetime) -> list[Reminder]:
        models = DjangoReminderModel.objects.filter(
            remind_at__lte=as_of,
        ).order_by("remind_at", "id")
        return [self._to_domain(model) for model in models]

    def delete_by_id(self, reminder_id: UUID) -> bool:
        deleted, _ = DjangoReminderModel.objects.filter(id=reminder_id).delete()
        return deleted > 0

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
        )
