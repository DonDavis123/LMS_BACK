from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.modules.notifications.domain.entities.notification import Notification
from src.modules.notifications.domain.enums.notification_type import NotificationType


class NotificationRepository(ABC):

    @abstractmethod
    def save(self, notification: Notification) -> Notification:
        pass

    @abstractmethod
    def get_by_id(self, notification_id: UUID) -> Notification | None:
        pass

    @abstractmethod
    def get_by_user(self, user_id: UUID) -> list[Notification]:
        pass

    @abstractmethod
    def get_unread_by_user(self, user_id: UUID) -> list[Notification]:
        pass

    @abstractmethod
    def get_active_by_user(
        self,
        user_id: UUID,
        as_of: datetime,
    ) -> list[Notification]:
        pass

    @abstractmethod
    def get_due(self, as_of: datetime) -> list[Notification]:
        pass

    @abstractmethod
    def get_existing_for_source(
        self,
        *,
        notification_type: NotificationType,
        scheduled_for: datetime,
        task_id: UUID | None = None,
        meeting_id: UUID | None = None,
        reminder_id: UUID | None = None,
    ) -> Notification | None:
        pass

    @abstractmethod
    def delete_by_id(self, notification_id: UUID) -> bool:
        pass

    @abstractmethod
    def delete_expired(self, as_of: datetime) -> int:
        pass

    @abstractmethod
    def delete_by_user_id(self, user_id: UUID) -> int:
        pass

    @abstractmethod
    def count_by_user_id(self, user_id: UUID) -> int:
        pass
