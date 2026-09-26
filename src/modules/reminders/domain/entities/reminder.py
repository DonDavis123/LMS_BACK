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
            raise ValueError(
                "A Reminder cannot be associated with both a Task and a Meeting."
            )

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

    def update(
        self,
        *,
        subject: str | None = None,
        remind_at: datetime | None = None,
        task_id: UUID | None = None,
        meeting_id: UUID | None = None,
        task_id_provided: bool = False,
        meeting_id_provided: bool = False,
    ) -> None:
        new_subject = self.subject if subject is None else subject
        if not isinstance(new_subject, str) or not new_subject.strip():
            raise ValueError("Reminder subject cannot be empty.")

        new_remind_at = self.remind_at if remind_at is None else remind_at
        if not isinstance(new_remind_at, datetime):
            raise ValueError("Reminder time must be a datetime.")

        new_task_id = task_id if task_id_provided else self.task_id
        new_meeting_id = meeting_id if meeting_id_provided else self.meeting_id

        if new_task_id is not None and new_meeting_id is not None:
            raise ValueError(
                "A Reminder cannot be associated with both a Task and a Meeting."
            )

        self.subject = new_subject.strip()
        self.remind_at = new_remind_at
        self.task_id = new_task_id
        self.meeting_id = new_meeting_id
        self.updated_at = datetime.now(timezone.utc)
