from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CreateReminderDTO:
    subject: str
    remind_at: datetime
    user_id: UUID
    task_id: UUID | None = None
    meeting_id: UUID | None = None
