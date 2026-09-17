from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

from ..enums.task_priority import TaskPriority
from ..enums.task_status import TaskStatus


@dataclass
class Task:
    id: UUID
    subject: str
    due_date: date | None
    priority: TaskPriority
    owner_id: UUID
    reminder_at: datetime | None
    lead_id: UUID | None
    contact_id: UUID | None
    account_id: UUID | None
    status: TaskStatus
    description: str | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    def soft_delete(self) -> None:
        if self.is_deleted:
            raise ValueError("Task is already deleted.")

        self.is_deleted = True

    @classmethod
    def create(
        cls,
        subject: str,
        owner_id: UUID,
        created_by_id: UUID,
        due_date: date | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        reminder_at: datetime | None = None,
        lead_id: UUID | None = None,
        contact_id: UUID | None = None,
        account_id: UUID | None = None,
        status: TaskStatus = TaskStatus.NOT_STARTED,
        description: str | None = None,
    ) -> "Task":
        now = datetime.utcnow()

        return cls(
            id=uuid4(),
            subject=subject,
            due_date=due_date,
            priority=priority,
            owner_id=owner_id,
            reminder_at=reminder_at,
            lead_id=lead_id,
            contact_id=contact_id,
            account_id=account_id,
            status=status,
            description=description,
            created_by_id=created_by_id,
            created_at=now,
            updated_at=now,
            is_deleted=False,
        )
