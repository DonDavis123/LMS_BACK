from src.modules.reminders.application.dto.create_reminder import CreateReminderDTO
from src.modules.reminders.application.interfaces.reminder_repository import ReminderRepository
from src.modules.reminders.domain.entities.reminder import Reminder
from src.modules.tasks.application.interfaces.task_repository import TaskRepository
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class CreateReminderUseCase:
    def __init__(
        self,
        reminder_repository: ReminderRepository,
        user_repository: UserRepository,
        task_repository: TaskRepository,
        meeting_repository: MeetingRepository,
        transaction_manager: TransactionManager,
    ):
        self.reminder_repository = reminder_repository
        self.user_repository = user_repository
        self.task_repository = task_repository
        self.meeting_repository = meeting_repository
        self.transaction_manager = transaction_manager

    def execute(self, data: CreateReminderDTO) -> Reminder:
        user = self.user_repository.get_by_id(data.user_id)
        if user is None:
            raise ValueError("Reminder user not found.")
        if not user.is_active:
            raise ValueError("Reminder user is inactive.")

        if data.task_id is not None:
            task = self.task_repository.get_by_id(data.task_id)
            if task is None or getattr(task, "is_deleted", False):
                raise ValueError("Selected task not found.")

        if data.meeting_id is not None:
            meeting = self.meeting_repository.get_by_id(data.meeting_id)
            if meeting is None:
                raise ValueError("Selected meeting not found.")

        reminder = Reminder.create(
            subject=data.subject,
            remind_at=data.remind_at,
            user_id=data.user_id,
            task_id=data.task_id,
            meeting_id=data.meeting_id,
        )

        return self.transaction_manager.execute(
            lambda: self.reminder_repository.save(reminder)
        )
