from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True)
class CalendarEventDTO:
    """One item on the calendar, normalised from a task, meeting, call or reminder."""

    id: UUID
    type: str  # TASK | MEETING | CALL | REMINDER
    title: str
    start: datetime | date
    end: datetime | date | None
    all_day: bool
    status: str | None
    owner_id: UUID | None
    owner_name: str | None
    related_record_type: str | None = None
    related_record_id: UUID | None = None
    related_record_name: str | None = None
    reminder_at: datetime | None = None
