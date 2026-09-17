from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.modules.tasks.domain.enums.task_priority import TaskPriority
from src.modules.tasks.domain.enums.task_status import TaskStatus


@dataclass
class CreateTaskDTO:
    subject: str
    owner_id: UUID
    created_by_id: UUID
    due_date: date | None = None
    priority: TaskPriority = TaskPriority.NORMAL
    reminder_at: datetime | None = None
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    account_id: UUID | None = None
    status: TaskStatus = TaskStatus.NOT_STARTED
    description: str | None = None
