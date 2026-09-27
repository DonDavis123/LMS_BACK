from uuid import UUID

from src.modules.notifications.application.interfaces.notification_repository import (
    NotificationRepository,
)


class GetNotificationsUseCase:
    def __init__(self, notification_repository: NotificationRepository):
        self.notification_repository = notification_repository

    def execute(
        self,
        current_user_id: UUID,
        *,
        as_of,
        unread_only: bool = False,
    ):
        if unread_only:
            return self.notification_repository.get_unread_by_user(current_user_id)
        return self.notification_repository.get_active_by_user(
            current_user_id,
            as_of,
        )
