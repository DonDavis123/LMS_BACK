from uuid import UUID

from src.modules.notifications.application.interfaces.notification_repository import (
    NotificationRepository,
)


class GetNotificationUseCase:
    def __init__(self, notification_repository: NotificationRepository):
        self.notification_repository = notification_repository

    def execute(
        self,
        notification_id: UUID,
        current_user_id: UUID,
    ):
        notification = self.notification_repository.get_by_id(notification_id)
        if notification is None or notification.user_id != current_user_id:
            return None
        return notification
