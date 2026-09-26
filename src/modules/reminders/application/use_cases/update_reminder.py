from uuid import UUID

from src.modules.reminders.application.dto.update_reminder import UpdateReminderDTO
from src.modules.reminders.application.interfaces.reminder_repository import ReminderRepository
from src.modules.reminders.domain.entities.reminder import Reminder
from src.modules.tasks.application.interfaces.task_repository import TaskRepository
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class UpdateReminderUseCase:
    def __init__(
        self,
        reminder_repository: ReminderRepository,
        task_repository: TaskRepository,
        meeting_repository: MeetingRepository,
        transaction_manager: TransactionManager,
    ):
        self.reminder_repository = reminder_repository
        self.task_repository = task_repository
        self.meeting_repository = meeting_repository
        self.transaction_manager = transaction_manager

    def execute(
        self,
        data: UpdateReminderDTO,
        current_user_id: UUID,
    ) -> Reminder:
        reminder = self.reminder_repository.get_by_id(data.reminder_id)

        if reminder is None or reminder.user_id != current_user_id:
            raise ValueError("Reminder not found.")

        fields = dict(data.fields)
        allowed_fields = {"subject", "remind_at", "task_id", "meeting_id"}
        unknown_fields = set(fields) - allowed_fields
        if unknown_fields:
            raise ValueError("Unsupported reminder field.")

        task_id_provided = "task_id" in fields
        meeting_id_provided = "meeting_id" in fields

        task_id = fields.get("task_id")
        meeting_id = fields.get("meeting_id")

        if task_id is not None:
            task = self.task_repository.get_by_id(task_id)
            if task is None or getattr(task, "is_deleted", False):
                raise ValueError("Selected task not found.")

        if meeting_id is not None:
            meeting = self.meeting_repository.get_by_id(meeting_id)
            if meeting is None:
                raise ValueError("Selected meeting not found.")

        def update():
            reminder.update(
                subject=fields.get("subject"),
                remind_at=fields.get("remind_at"),
                task_id=task_id,
                meeting_id=meeting_id,
                task_id_provided=task_id_provided,
                meeting_id_provided=meeting_id_provided,
            )
            return self.reminder_repository.save(reminder)

        return self.transaction_manager.execute(update)
