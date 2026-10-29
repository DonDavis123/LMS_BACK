from src.modules.notifications.application.dto.create_notification import (
    CreateNotificationDTO,
)
from src.modules.notifications.application.interfaces.notification_repository import (
    NotificationRepository,
)
from src.modules.notifications.domain.entities.notification import Notification
from src.modules.reminders.application.interfaces.reminder_repository import (
    ReminderRepository,
)
from src.modules.tasks.application.interfaces.task_repository import TaskRepository
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class CreateNotificationUseCase:
    def __init__(
        self,
        notification_repository: NotificationRepository,
        user_repository: UserRepository,
        task_repository: TaskRepository,
        meeting_repository: MeetingRepository,
        reminder_repository: ReminderRepository,
        transaction_manager: TransactionManager,
    ):
        self.notification_repository = notification_repository
        self.user_repository = user_repository
        self.task_repository = task_repository
        self.meeting_repository = meeting_repository
        self.reminder_repository = reminder_repository
        self.transaction_manager = transaction_manager

    def execute(self, data: CreateNotificationDTO) -> Notification:
        user = self.user_repository.get_by_id(data.user_id)
        if user is None:
            raise ValueError("Notification user not found.")
        if not user.is_active:
            raise ValueError("Notification user is inactive.")

        if data.task_id is not None and data.meeting_id is not None:
            raise ValueError(
                "A Notification cannot be associated with both a Task and a Meeting."
            )

        if data.task_id is not None:
            task = self.task_repository.get_by_id(data.task_id)
            if task is None or getattr(task, "is_deleted", False):
                raise ValueError("Selected task not found.")

        if data.meeting_id is not None:
            meeting = self.meeting_repository.get_by_id(data.meeting_id)
            if meeting is None or getattr(meeting, "is_deleted", False):
                raise ValueError("Selected meeting not found.")

        if data.reminder_id is not None:
            reminder = self.reminder_repository.get_by_id(data.reminder_id)
            if reminder is None:
                raise ValueError("Selected reminder not found.")
            if reminder.user_id != data.user_id:
                # A task reminder is also delivered to the task's assignee.
                reminder_task = (
                    self.task_repository.get_by_id(reminder.task_id)
                    if reminder.task_id is not None
                    else None
                )
                if (
                    reminder_task is None
                    or reminder_task.assigned_to_id != data.user_id
                ):
                    raise ValueError("Selected reminder does not belong to the notification user.")

        notification = Notification.create(
            notification_type=data.notification_type,
            title=data.title,
            message=data.message,
            user_id=data.user_id,
            scheduled_for=data.scheduled_for,
            task_id=data.task_id,
            meeting_id=data.meeting_id,
            reminder_id=data.reminder_id,
            lead_import_job_id=data.lead_import_job_id,
        )

        def creation():
            source = {}
            if notification.lead_import_job_id is not None:
                # Only passed when set, so every other notification type is
                # looked up exactly as before.
                source["lead_import_job_id"] = notification.lead_import_job_id
            existing = self.notification_repository.get_existing_for_source(
                notification_type=notification.notification_type,
                scheduled_for=notification.scheduled_for,
                task_id=notification.task_id,
                meeting_id=notification.meeting_id,
                reminder_id=notification.reminder_id,
                user_id=notification.user_id,
                **source,
            )
            if existing is not None:
                return existing
            return self.notification_repository.save(notification)

        return self.transaction_manager.execute(creation)
