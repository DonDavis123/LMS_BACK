from datetime import datetime, timedelta
from uuid import UUID

from django.db import IntegrityError

from src.modules.notifications.application.interfaces.notification_repository import (
    NotificationRepository,
)
from src.modules.notifications.domain.entities.notification import Notification
from src.modules.notifications.domain.enums.notification_type import NotificationType

from .models import DjangoNotificationModel


class DjangoNotificationRepository(NotificationRepository):

    def save(self, notification: Notification) -> Notification:
        notification.validate_state()

        if notification.task_id is not None and notification.meeting_id is not None:
            raise ValueError(
                "A Notification cannot be associated with both a Task and a Meeting."
            )

        try:
            model, _ = DjangoNotificationModel.objects.update_or_create(
                id=notification.id,
                defaults={
                    "notification_type": notification.notification_type.value,
                    "title": notification.title,
                    "message": notification.message,
                    "user_id": notification.user_id,
                    "task_id": notification.task_id,
                    "meeting_id": notification.meeting_id,
                    "reminder_id": notification.reminder_id,
                    "scheduled_for": notification.scheduled_for,
                    "expires_at": notification.expires_at,
                    "is_read": notification.is_read,
                    "read_at": notification.read_at,
                "dismissed_at": notification.dismissed_at,
                },
            )
        except IntegrityError:
            existing = self.get_existing_for_source(
                notification_type=notification.notification_type,
                scheduled_for=notification.scheduled_for,
                task_id=notification.task_id,
                meeting_id=notification.meeting_id,
                reminder_id=notification.reminder_id,
            )
            if existing is None:
                raise
            return existing
        return self._to_domain(model)

    def get_by_id(self, notification_id: UUID) -> Notification | None:
        try:
            model = DjangoNotificationModel.objects.get(id=notification_id)
        except DjangoNotificationModel.DoesNotExist:
            return None
        return self._to_domain(model)

    def get_by_user(self, user_id: UUID) -> list[Notification]:
        models = (
            DjangoNotificationModel.objects
            .filter(user_id=user_id)
            .order_by("-scheduled_for", "-id")
        )
        return [self._to_domain(model) for model in models]

    def get_unread_by_user(self, user_id: UUID) -> list[Notification]:
        models = (
            DjangoNotificationModel.objects
            .filter(user_id=user_id, is_read=False)
            .order_by("-scheduled_for", "-id")
        )
        return [self._to_domain(model) for model in models]

    def get_active_by_user(
        self,
        user_id: UUID,
        as_of: datetime,
    ) -> list[Notification]:
        models = (
            DjangoNotificationModel.objects
            .filter(
                user_id=user_id,
                expires_at__gt=as_of,
            )
            .order_by("-scheduled_for", "-id")
        )
        return [self._to_domain(model) for model in models]

    def get_due(self, as_of: datetime) -> list[Notification]:
        models = (
            DjangoNotificationModel.objects
            .filter(
                scheduled_for__lte=as_of,
                expires_at__gt=as_of,
            )
            .order_by("scheduled_for", "id")
        )
        return [self._to_domain(model) for model in models]

    def get_existing_for_source(
        self,
        *,
        notification_type: NotificationType,
        scheduled_for: datetime,
        task_id: UUID | None = None,
        meeting_id: UUID | None = None,
        reminder_id: UUID | None = None,
    ) -> Notification | None:
        queryset = DjangoNotificationModel.objects.filter(
            notification_type=notification_type.value,
            scheduled_for=scheduled_for,
        )

        if task_id is not None:
            queryset = queryset.filter(task_id=task_id)
        else:
            queryset = queryset.filter(task_id__isnull=True)

        if meeting_id is not None:
            queryset = queryset.filter(meeting_id=meeting_id)
        else:
            queryset = queryset.filter(meeting_id__isnull=True)

        if reminder_id is not None:
            queryset = queryset.filter(reminder_id=reminder_id)
        else:
            queryset = queryset.filter(reminder_id__isnull=True)

        model = queryset.order_by("id").first()
        return self._to_domain(model) if model else None

    def delete_by_id(self, notification_id: UUID) -> bool:
        deleted, _ = DjangoNotificationModel.objects.filter(
            id=notification_id,
        ).delete()
        return deleted > 0

    def delete_by_user_id(self, user_id: UUID) -> int:
        deleted, _ = DjangoNotificationModel.objects.filter(
            user_id=user_id,
        ).delete()
        return deleted

    def delete_expired(self, as_of: datetime) -> int:
        natural_expired = DjangoNotificationModel.objects.filter(
            expires_at__lte=as_of,
            dismissed_at__isnull=True,
        )
        dismissed_expired = DjangoNotificationModel.objects.filter(
            dismissed_at__isnull=False,
            dismissed_at__lte=as_of - timedelta(days=15),
        )
        deleted_natural, _ = natural_expired.delete()
        deleted_dismissed, _ = dismissed_expired.delete()
        return deleted_natural + deleted_dismissed

    @staticmethod
    def _to_domain(model: DjangoNotificationModel) -> Notification:
        notification = Notification(
            id=model.id,
            notification_type=NotificationType(model.notification_type),
            title=model.title,
            message=model.message,
            user_id=model.user_id,
            task_id=model.task_id,
            meeting_id=model.meeting_id,
            reminder_id=model.reminder_id,
            scheduled_for=model.scheduled_for,
            expires_at=model.expires_at,
            is_read=model.is_read,
            read_at=model.read_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            dismissed_at=model.dismissed_at,
        )
        notification.validate_state()
        return notification
