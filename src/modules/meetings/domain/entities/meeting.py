from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class Meeting:
    id: UUID
    title: str
    description: str | None
    location: str | None
    is_all_day: bool
    start_at: datetime
    end_at: datetime
    host_id: UUID
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    @classmethod
    def create(
        cls,
        title: str,
        start_at: datetime,
        end_at: datetime,
        host_id: UUID,
        created_by_id: UUID,
        description: str | None = None,
        location: str | None = None,
        is_all_day: bool = False,
    ) -> "Meeting":
        if not title or not title.strip():
            raise ValueError("Meeting title cannot be empty.")

        if end_at < start_at:
            raise ValueError("Meeting end time cannot be earlier than start time.")

        if not host_id:
            raise ValueError("Meeting host is required.")

        if not created_by_id:
            raise ValueError("Meeting creator is required.")

        now = datetime.now(timezone.utc)

        return cls(
            id=uuid4(),
            title=title,
            description=description,
            location=location,
            is_all_day=is_all_day,
            start_at=start_at,
            end_at=end_at,
            host_id=host_id,
            created_by_id=created_by_id,
            created_at=now,
            updated_at=now,
            is_deleted=False,
        )

    def soft_delete(self) -> None:
        if self.is_deleted:
            raise ValueError("Meeting is already deleted.")

        self.is_deleted = True
