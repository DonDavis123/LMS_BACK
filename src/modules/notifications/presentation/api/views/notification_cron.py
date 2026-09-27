import hmac
import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.meetings.infrastructure.persistence.django_meeting_repository import (
    DjangoMeetingRepository,
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
            response = Response(
                {"detail": "Invalid cron credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            response["Cache-Control"] = "no-store"
            return response

        if not hmac.compare_digest(provided_secret, configured_secret):
            response = Response(
                {"detail": "Invalid cron credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            response["Cache-Control"] = "no-store"
            return response

        now = timezone.now()

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
            logger.exception("Notification cron processing failed")
            response = Response(
                {"detail": "Notification processing failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            response["Cache-Control"] = "no-store"
            return response

        logger.info("Notification cron processing completed")

        response = Response(
            {
                "status": "processed",
                "reminders_processed": result.reminders_processed,
                "task_notifications_created": result.task_notifications_created,
                "meeting_notifications_created": result.meeting_notifications_created,
                "duplicates_skipped": result.duplicates_skipped,
                "expired_notifications_deleted": result.expired_notifications_deleted,
                "failures": result.failures,
            },
            status=status.HTTP_200_OK,
        )
        # Cron responses contain processing metadata and must not be cached.
        response["Cache-Control"] = "no-store"
        return response
