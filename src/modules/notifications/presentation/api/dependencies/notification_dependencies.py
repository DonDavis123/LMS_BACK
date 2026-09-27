from src.modules.meetings.infrastructure.persistence.django_meeting_repository import DjangoMeetingRepository
from src.modules.notifications.application.use_cases.delete_notification import DeleteNotificationUseCase
from src.modules.notifications.application.use_cases.get_notification import GetNotificationUseCase
from src.modules.notifications.application.use_cases.get_notifications import GetNotificationsUseCase
from src.modules.notifications.application.use_cases.mark_notification_read import MarkNotificationReadUseCase
from src.modules.notifications.infrastructure.persistence.django_notification_repository import DjangoNotificationRepository
from src.modules.reminders.infrastructure.persistence.django_reminder_repository import DjangoReminderRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository


def transaction_manager():
    return DjangoTransactionManager()


def get_notifications_use_case() -> GetNotificationsUseCase:
    return GetNotificationsUseCase(DjangoNotificationRepository())


def get_notification_use_case() -> GetNotificationUseCase:
    return GetNotificationUseCase(DjangoNotificationRepository())


def get_mark_notification_read_use_case() -> MarkNotificationReadUseCase:
    return MarkNotificationReadUseCase(DjangoNotificationRepository(), transaction_manager())


def get_delete_notification_use_case() -> DeleteNotificationUseCase:
    return DeleteNotificationUseCase(DjangoNotificationRepository(), transaction_manager())
