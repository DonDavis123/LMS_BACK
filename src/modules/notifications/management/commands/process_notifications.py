import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from src.modules.meetings.infrastructure.persistence.django_meeting_repository import DjangoMeetingRepository
from src.modules.notifications.application.use_cases.process_notifications import ProcessNotificationsUseCase
from src.modules.notifications.infrastructure.persistence.django_notification_repository import DjangoNotificationRepository
from src.modules.reminders.infrastructure.persistence.django_reminder_repository import DjangoReminderRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process due reminders and task/meeting notification events once."

    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(f"Processing notifications at {now.isoformat()}")
        try:
            result = ProcessNotificationsUseCase(
                notification_repository=DjangoNotificationRepository(),
                reminder_repository=DjangoReminderRepository(),
                task_repository=DjangoTaskRepository(),
                meeting_repository=DjangoMeetingRepository(),
                user_repository=DjangoUserRepository(),
                transaction_manager=DjangoTransactionManager(),
            ).execute(now, timezone.localtime(now))
        except Exception:
            logger.exception("Notification processing failed")
            self.stderr.write(self.style.ERROR("Notification processing failed."))
            raise

        self.stdout.write(self.style.SUCCESS("Notification processing completed."))
        self.stdout.write(f"Reminders processed: {result.reminders_processed}")
        self.stdout.write(f"Reminders deleted: {result.reminders_deleted}")
        self.stdout.write(f"Task notifications created: {result.task_notifications_created}")
        self.stdout.write(f"Meeting notifications created: {result.meeting_notifications_created}")
        self.stdout.write(f"Duplicates skipped: {result.duplicates_skipped}")
        self.stdout.write(f"Expired notifications deleted: {result.expired_notifications_deleted}")
        self.stdout.write(f"Failures: {result.failures}")
