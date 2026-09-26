from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class Reminder:
    id: UUID
    subject: str
    remind_at: datetime
    user_id: UUID
    task_id: UUID | None
    meeting_id: UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        subject: str,
        remind_at: datetime,
        user_id: UUID,
        task_id: UUID | None = None,
        meeting_id: UUID | None = None,
    ) -> "Reminder":
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("Reminder subject cannot be empty.")

        if remind_at is None:
            raise ValueError("Reminder time is required.")

        if not isinstance(remind_at, datetime):
            raise ValueError("Reminder time must be a datetime.")

        if not user_id:
            raise ValueError("Reminder user is required.")

        if task_id is not None and meeting_id is not None:
            raise ValueError("A Reminder cannot be associated with both a Task and a Meeting.")

        now = datetime.now(timezone.utc)
        return cls(
            id=uuid4(),
            subject=subject.strip(),
            remind_at=remind_at,
            user_id=user_id,
            task_id=task_id,
            meeting_id=meeting_id,
            created_at=now,
            updated_at=now,
        )
