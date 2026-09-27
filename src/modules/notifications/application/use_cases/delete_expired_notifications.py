from datetime import datetime

from src.modules.notifications.application.interfaces.notification_repository import (
    NotificationRepository,
)
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class DeleteExpiredNotificationsUseCase:
    def __init__(
        self,
        notification_repository: NotificationRepository,
        transaction_manager: TransactionManager,
    ):
        self.notification_repository = notification_repository
        self.transaction_manager = transaction_manager

    def execute(self, as_of: datetime) -> int:
        return self.transaction_manager.execute(
            lambda: self.notification_repository.delete_expired(as_of)
        )
