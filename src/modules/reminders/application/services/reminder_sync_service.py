from uuid import UUID

from src.modules.reminders.application.interfaces.reminder_repository import ReminderRepository
from src.modules.reminders.domain.entities.reminder import Reminder


class ReminderSyncService:
    """Synchronizes reminders that are owned by Tasks or Meetings."""

    def __init__(self, reminder_repository: ReminderRepository):
        self.reminder_repository = reminder_repository

    def sync_task(self, task) -> None:
        reminders = self.reminder_repository.get_by_task(task.id)

        if task.is_deleted or task.reminder_at is None:
            for reminder in reminders:
                self.reminder_repository.delete_by_id(reminder.id)
            return

        self._ensure_single_related_reminder(
            reminders,
            "Task",
            task.id,
        )

        if reminders:
            reminder = reminders[0]
            reminder.synchronize(
                subject=task.subject,
                remind_at=task.reminder_at,
                user_id=task.owner_id,
            )
            self.reminder_repository.save(reminder)
            return

        reminder = Reminder.create(
            subject=task.subject,
            remind_at=task.reminder_at,
            user_id=task.owner_id,
            task_id=task.id,
        )
        self.reminder_repository.save(reminder)

    def sync_meeting(self, meeting) -> None:
        reminders = self.reminder_repository.get_by_meeting(meeting.id)

        if meeting.is_deleted or meeting.reminder_at is None:
            for reminder in reminders:
                self.reminder_repository.delete_by_id(reminder.id)
            return

        self._ensure_single_related_reminder(
            reminders,
            "Meeting",
            meeting.id,
        )

        if reminders:
            reminder = reminders[0]
            reminder.synchronize(
                subject=meeting.title,
                remind_at=meeting.reminder_at,
                user_id=meeting.host_id,
            )
            self.reminder_repository.save(reminder)
            return

        reminder = Reminder.create(
            subject=meeting.title,
            remind_at=meeting.reminder_at,
            user_id=meeting.host_id,
            meeting_id=meeting.id,
        )
        self.reminder_repository.save(reminder)

    def delete_for_task(self, task_id: UUID) -> None:
        for reminder in self.reminder_repository.get_by_task(task_id):
            self.reminder_repository.delete_by_id(reminder.id)

    def delete_for_meeting(self, meeting_id: UUID) -> None:
        for reminder in self.reminder_repository.get_by_meeting(meeting_id):
            self.reminder_repository.delete_by_id(reminder.id)

    @staticmethod
    def _ensure_single_related_reminder(reminders, record_type: str, record_id: UUID) -> None:
        if len(reminders) > 1:
            raise ValueError(
                f"Multiple automatic reminders exist for {record_type} {record_id}. "
                "Resolve the duplicate reminders before updating this record."
            )
