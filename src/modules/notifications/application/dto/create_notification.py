from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.notifications.domain.enums.notification_type import NotificationType


@dataclass(frozen=True)
class CreateNotificationDTO:
    notification_type: NotificationType
    title: str
    message: str
    user_id: UUID
    scheduled_for: datetime
    task_id: UUID | None = None
    meeting_id: UUID | None = None
    reminder_id: UUID | None = None
