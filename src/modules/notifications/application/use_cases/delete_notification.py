from uuid import UUID

from src.modules.notifications.application.interfaces.notification_repository import (
    NotificationRepository,
)
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class DeleteNotificationUseCase:
    def __init__(
        self,
        notification_repository: NotificationRepository,
        transaction_manager: TransactionManager,
    ):
        self.notification_repository = notification_repository
        self.transaction_manager = transaction_manager

    def execute(
        self,
        notification_id: UUID,
        current_user_id: UUID,
    ) -> None:
        notification = self.notification_repository.get_by_id(notification_id)
        if notification is None or notification.user_id != current_user_id:
            raise ValueError("Notification not found.")

        def deletion():
            if not self.notification_repository.delete_by_id(notification_id):
                raise ValueError("Notification not found.")

        self.transaction_manager.execute(deletion)
