from uuid import UUID

from src.modules.reminders.application.interfaces.reminder_repository import ReminderRepository


class GetRemindersUseCase:
    def __init__(self, reminder_repository: ReminderRepository):
        self.reminder_repository = reminder_repository

    def execute(
        self,
        current_user_id: UUID,
        task_id: UUID | None = None,
        meeting_id: UUID | None = None,
    ):
        if task_id is not None and meeting_id is not None:
            raise ValueError(
                "A reminder cannot be filtered by both Task and Meeting."
            )

        if task_id is not None:
            reminders = self.reminder_repository.get_by_task(task_id)
        elif meeting_id is not None:
            reminders = self.reminder_repository.get_by_meeting(meeting_id)
        else:
            reminders = self.reminder_repository.get_by_user(current_user_id)

        return [
            reminder
            for reminder in reminders
            if reminder.user_id == current_user_id
        ]
