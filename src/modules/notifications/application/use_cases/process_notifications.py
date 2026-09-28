from datetime import datetime, time, timedelta

from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.notifications.application.dto.create_notification import CreateNotificationDTO
from src.modules.notifications.application.dto.process_notifications import ProcessNotificationsResult
from src.modules.notifications.application.interfaces.notification_repository import NotificationRepository
from src.modules.notifications.application.use_cases.create_notification import CreateNotificationUseCase
from src.modules.notifications.application.use_cases.delete_expired_notifications import DeleteExpiredNotificationsUseCase
from src.modules.notifications.domain.enums.notification_type import NotificationType
from src.modules.reminders.application.interfaces.reminder_repository import ReminderRepository
from src.modules.tasks.application.interfaces.task_repository import TaskRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.users.application.interfaces.user_repository import UserRepository


class ProcessNotificationsUseCase:
    """Orchestrates scheduled notification generation without using Django ORM directly."""

    def __init__(
        self,
        notification_repository: NotificationRepository,
        reminder_repository: ReminderRepository,
        task_repository: TaskRepository,
        meeting_repository: MeetingRepository,
        user_repository: UserRepository,
        transaction_manager: TransactionManager,
    ):
        self.notification_repository = notification_repository
        self.reminder_repository = reminder_repository
        self.task_repository = task_repository
        self.meeting_repository = meeting_repository
        self.user_repository = user_repository
        self.transaction_manager = transaction_manager
        self.create_notification = CreateNotificationUseCase(
            notification_repository,
            user_repository,
            task_repository,
            meeting_repository,
            reminder_repository,
            transaction_manager,
        )
        self.delete_expired = DeleteExpiredNotificationsUseCase(
            notification_repository,
            transaction_manager,
        )

    def execute(self, as_of: datetime, local_now: datetime | None = None) -> ProcessNotificationsResult:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("Notification processing time must be timezone-aware.")
        now = as_of
        local_now = local_now or as_of
        if local_now.tzinfo is None or local_now.utcoffset() is None:
            raise ValueError("Notification local processing time must be timezone-aware.")
        today = local_now.date()
        tomorrow = today + timedelta(days=1)

        reminders_processed = 0
        reminders_deleted = 0
        task_created = 0
        meeting_created = 0
        duplicates = 0
        failures = 0

        for reminder in self.reminder_repository.get_due(now):
            reminders_processed += 1
            try:
                def process_reminder():
                    _, duplicate = self._create_reminder_notification(reminder)

                    # A reminder is a one-time scheduling record. Once its
                    # notification has been successfully created (or an
                    # existing notification proves it was already created),
                    # consume the reminder in the same transaction.
                    deleted = self.reminder_repository.delete_by_id(reminder.id)
                    if not deleted:
                        raise ValueError("Due reminder could not be deleted.")

                    return duplicate

                duplicate = self.transaction_manager.execute(process_reminder)

                if duplicate:
                    duplicates += 1
                reminders_deleted += 1
            except ValueError:
                failures += 1

        task_events = self.task_repository.get_by_due_date_range(today, tomorrow)
        for task in task_events:
            notification_type = (
                NotificationType.TASK_DUE_TODAY
                if task.due_date == today
                else NotificationType.TASK_DUE_ONE_DAY
            )
            scheduled_for = self._local_midnight(today if task.due_date == today else tomorrow, local_now.tzinfo)
            try:
                created, duplicate = self._create_task_notification(
                    task,
                    notification_type,
                    scheduled_for,
                )
                if duplicate:
                    duplicates += 1
                elif created:
                    task_created += 1
            except ValueError:
                failures += 1

        start_today = self._local_midnight(today, local_now.tzinfo)
        start_after_tomorrow = self._local_midnight(tomorrow + timedelta(days=1), local_now.tzinfo)
        meetings = self.meeting_repository.get_by_start_at_range(
            start_today,
            start_after_tomorrow,
        )
        for meeting in meetings:
            meeting_local_date = meeting.start_at.astimezone(local_now.tzinfo).date()
            if meeting_local_date == today:
                notification_type = NotificationType.MEETING_TODAY
                scheduled_for = self._local_midnight(today, local_now.tzinfo)
            elif meeting_local_date == tomorrow:
                notification_type = NotificationType.MEETING_ONE_DAY
                scheduled_for = self._local_midnight(today, local_now.tzinfo)
            else:
                continue


            try:
                created, duplicate = self._create_meeting_notification(
                    meeting,
                    notification_type,
                    scheduled_for,
                )
                if duplicate:
                    duplicates += 1
                elif created:
                    meeting_created += 1
            except ValueError:
                failures += 1

        expired_deleted = self.delete_expired.execute(now)

        return ProcessNotificationsResult(
            reminders_processed=reminders_processed,
            reminders_deleted=reminders_deleted,
            task_notifications_created=task_created,
            meeting_notifications_created=meeting_created,
            duplicates_skipped=duplicates,
            expired_notifications_deleted=expired_deleted,
            failures=failures,
        )

    def _create_reminder_notification(self, reminder):
        existing = self.notification_repository.get_existing_for_source(
            notification_type=NotificationType.REMINDER,
            scheduled_for=reminder.remind_at,
            task_id=reminder.task_id,
            meeting_id=reminder.meeting_id,
            reminder_id=reminder.id,
        )
        if existing is not None:
            return existing, True
        notification = self.create_notification.execute(
            CreateNotificationDTO(
                notification_type=NotificationType.REMINDER,
                title="Reminder",
                message=reminder.subject,
                user_id=reminder.user_id,
                scheduled_for=reminder.remind_at,
                task_id=reminder.task_id,
                meeting_id=reminder.meeting_id,
                reminder_id=reminder.id,
            )
        )
        return notification, False

    def _create_task_notification(self, task, notification_type, scheduled_for):
        existing = self.notification_repository.get_existing_for_source(
            notification_type=notification_type,
            scheduled_for=scheduled_for,
            task_id=task.id,
        )
        if existing is not None:
            return existing, True
        notification = self.create_notification.execute(
            CreateNotificationDTO(
                notification_type=notification_type,
                title=("Task due today" if notification_type == NotificationType.TASK_DUE_TODAY else "Task due tomorrow"),
                message=(
                    f"{task.subject} is due today."
                    if notification_type == NotificationType.TASK_DUE_TODAY
                    else f"{task.subject} is due tomorrow."
                ),
                user_id=task.owner_id,
                scheduled_for=scheduled_for,
                task_id=task.id,
            )
        )
        return notification, False

    def _create_meeting_notification(self, meeting, notification_type, scheduled_for):
        existing = self.notification_repository.get_existing_for_source(
            notification_type=notification_type,
            scheduled_for=scheduled_for,
            meeting_id=meeting.id,
        )
        if existing is not None:
            return existing, True
        notification = self.create_notification.execute(
            CreateNotificationDTO(
                notification_type=notification_type,
                title=("Meeting today" if notification_type == NotificationType.MEETING_TODAY else "Meeting tomorrow"),
                message=(
                    f"{meeting.title} starts today."
                    if notification_type == NotificationType.MEETING_TODAY
                    else f"{meeting.title} starts tomorrow."
                ),
                user_id=meeting.host_id,
                scheduled_for=scheduled_for,
                meeting_id=meeting.id,
            )
        )
        return notification, False

    @staticmethod
    def _local_midnight(day, tzinfo):
        return datetime.combine(day, time.min, tzinfo=tzinfo)
