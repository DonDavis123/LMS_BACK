import hmac
import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.companies.infrastructure.persistence.active_companies import (
    get_active_company_ids,
)
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import (
    DjangoMeetingRepository,
)
from src.modules.notifications.application.dto.process_notifications import (
    ProcessNotificationsResult,
)
from src.modules.notifications.application.use_cases.process_notifications import (
    ProcessNotificationsUseCase,
)
from src.modules.notifications.infrastructure.persistence.django_notification_repository import (
    DjangoNotificationRepository,
)
from src.modules.reminders.infrastructure.persistence.django_reminder_repository import (
    DjangoReminderRepository,
)
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from src.modules.tasks.infrastructure.persistence.django_task_repository import (
    DjangoTaskRepository,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)

logger = logging.getLogger(__name__)

CRON_SECRET_HEADER = "X-Cron-Secret"


class NotificationCronProcessView(APIView):
    """
    Internal machine-to-machine trigger for scheduled notification processing.

    Authentication is deliberately separate from the normal JWT flow because
    this endpoint is intended for an external scheduler, not application users.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        configured_secret = getattr(settings, "NOTIFICATION_CRON_SECRET", None)
        provided_secret = request.headers.get(CRON_SECRET_HEADER)

        if not configured_secret or not provided_secret:
            return Response(
                {"detail": "Invalid cron credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not hmac.compare_digest(provided_secret, configured_secret):
            return Response(
                {"detail": "Invalid cron credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        now = timezone.now()

        try:
            result = ProcessNotificationsResult()
            for company_id in get_active_company_ids():
                try:
                    company_result = ProcessNotificationsUseCase(
                        notification_repository=DjangoNotificationRepository(company_id=company_id),
                        reminder_repository=DjangoReminderRepository(company_id=company_id),
                        task_repository=DjangoTaskRepository(company_id=company_id),
                        meeting_repository=DjangoMeetingRepository(company_id=company_id),
                        user_repository=DjangoUserRepository(company_id=company_id),
                        transaction_manager=DjangoTransactionManager(),
                    ).execute(now, timezone.localtime(now))
                    result = result + company_result
                except Exception:
                    logger.exception("Notification processing failed for company_id=%s", company_id)
                    result = result + ProcessNotificationsResult(failures=1)
        except Exception:
            logger.exception("Notification cron processing failed")
            return Response(
                {"detail": "Notification processing failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info("Notification cron processing completed")

        return Response(
            {
                "status": "processed",
                "reminders_processed": result.reminders_processed,
                "reminders_deleted": result.reminders_deleted,
                "task_notifications_created": result.task_notifications_created,
                "meeting_notifications_created": result.meeting_notifications_created,
                "duplicates_skipped": result.duplicates_skipped,
                "expired_notifications_deleted": result.expired_notifications_deleted,
                "failures": result.failures,
            },
            status=status.HTTP_200_OK,
        )
