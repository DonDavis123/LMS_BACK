from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.modules.calendar.application.dto.calendar_event import CalendarEventDTO


class CalendarRepository(ABC):
    """Read-only access to everything that can appear on the calendar.

    ``user_id`` limits the result to items the user owns / is assigned to /
    hosts / participates in; ``None`` returns the whole company.
    """

    @abstractmethod
    def get_tasks(
        self, *, start: datetime, end: datetime, user_id: UUID | None
    ) -> list[CalendarEventDTO]:
        pass

    @abstractmethod
    def get_meetings(
        self, *, start: datetime, end: datetime, user_id: UUID | None
    ) -> list[CalendarEventDTO]:
        pass

    @abstractmethod
    def get_calls(
        self, *, start: datetime, end: datetime, user_id: UUID | None
    ) -> list[CalendarEventDTO]:
        pass

    @abstractmethod
    def get_reminders(
        self, *, start: datetime, end: datetime, user_id: UUID | None
    ) -> list[CalendarEventDTO]:
        """Standalone reminders only (not those attached to a task or meeting)."""
        pass
