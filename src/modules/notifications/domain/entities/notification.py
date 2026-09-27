from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from ..enums.notification_type import NotificationType


NOTIFICATION_RETENTION_DAYS = 15


@dataclass
class Notification:
    id: UUID
    notification_type: NotificationType
    title: str
    message: str
    user_id: UUID
    task_id: UUID | None
    meeting_id: UUID | None
    reminder_id: UUID | None
    scheduled_for: datetime
    expires_at: datetime
    is_read: bool
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        notification_type: NotificationType,
        title: str,
        message: str,
        user_id: UUID,
        scheduled_for: datetime,
        task_id: UUID | None = None,
        meeting_id: UUID | None = None,
        reminder_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> "Notification":
        if not isinstance(notification_type, NotificationType):
            try:
                notification_type = NotificationType(notification_type)
            except (TypeError, ValueError) as exc:
                raise ValueError("Invalid notification type.") from exc

        if not isinstance(title, str) or not title.strip():
            raise ValueError("Notification title cannot be empty.")

        if not isinstance(message, str) or not message.strip():
            raise ValueError("Notification message cannot be empty.")

        if not user_id:
            raise ValueError("Notification user is required.")

        cls._validate_datetime(scheduled_for, "Notification scheduled time")

        if task_id is not None and meeting_id is not None:
            raise ValueError(
                "A Notification cannot be associated with both a Task and a Meeting."
            )

        now = created_at or datetime.now(timezone.utc)
        cls._validate_datetime(now, "Notification creation time")

        expires_at = now + timedelta(days=NOTIFICATION_RETENTION_DAYS)

        return cls(
            id=uuid4(),
            notification_type=notification_type,
            title=title.strip(),
            message=message.strip(),
            user_id=user_id,
            task_id=task_id,
            meeting_id=meeting_id,
            reminder_id=reminder_id,
            scheduled_for=scheduled_for,
            expires_at=expires_at,
            is_read=False,
            read_at=None,
            created_at=now,
            updated_at=now,
        )

    def mark_as_read(self, read_at: datetime | None = None) -> None:
        if self.is_read:
            return

        timestamp = read_at or datetime.now(timezone.utc)
        self._validate_datetime(timestamp, "Notification read time")
        self.is_read = True
        self.read_at = timestamp
        self.updated_at = timestamp

    def validate_state(self) -> None:
        if self.expires_at <= self.created_at:
            raise ValueError("Notification expiry must be later than creation time.")

        if self.is_read and self.read_at is None:
            raise ValueError("Read notifications must have a read time.")

        if not self.is_read and self.read_at is not None:
            raise ValueError("Unread notifications cannot have a read time.")

        if self.task_id is not None and self.meeting_id is not None:
            raise ValueError(
                "A Notification cannot be associated with both a Task and a Meeting."
            )

    @staticmethod
    def _validate_datetime(value: datetime | None, label: str) -> None:
        if value is None:
            raise ValueError(f"{label} is required.")
        if not isinstance(value, datetime):
            raise ValueError(f"{label} must be a datetime.")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware.")
