from uuid import UUID

from src.modules.reminders.application.interfaces.reminder_repository import ReminderRepository


class GetReminderUseCase:
    def __init__(self, reminder_repository: ReminderRepository):
        self.reminder_repository = reminder_repository

    def execute(self, reminder_id: UUID, current_user_id: UUID | None = None):
        reminder = self.reminder_repository.get_by_id(reminder_id)
        if reminder is None:
            return None

        if current_user_id is not None and reminder.user_id != current_user_id:
            return None

        return reminder
