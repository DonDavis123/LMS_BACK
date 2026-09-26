from uuid import UUID

from src.modules.reminders.application.interfaces.reminder_repository import ReminderRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class DeleteReminderUseCase:
    def __init__(
        self,
        reminder_repository: ReminderRepository,
        transaction_manager: TransactionManager,
    ):
        self.reminder_repository = reminder_repository
        self.transaction_manager = transaction_manager

    def execute(
        self,
        reminder_id: UUID,
        current_user_id: UUID,
    ) -> None:
        reminder = self.reminder_repository.get_by_id(reminder_id)

        if reminder is None or reminder.user_id != current_user_id:
            raise ValueError("Reminder not found.")

        def deletion():
            deleted = self.reminder_repository.delete_by_id(reminder_id)
            if not deleted:
                raise ValueError("Reminder not found.")

        self.transaction_manager.execute(deletion)
