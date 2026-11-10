from datetime import datetime, timedelta
from uuid import UUID

from src.modules.calendar.application.dto.calendar_event import CalendarEventDTO
from src.modules.calendar.application.interfaces.calendar_repository import (
    CalendarRepository,
)
from src.modules.users.domain.entities.role import UserRole

EVENT_TYPES = ("TASK", "MEETING", "CALL", "REMINDER")
MAX_RANGE = timedelta(days=62)

# Roles allowed to look at other people's calendars.
TEAM_VIEW_ROLES = {
    UserRole.SUPERADMIN.value,
    UserRole.ADMIN.value,
    UserRole.SALES_MANAGER.value,
}


class GetCalendarEventsUseCase:
    """Return the calendar items of a date range as one sorted list.

    Default view is "mine". Managers may pass ``scope="team"`` for the whole
    company or ``owner_id`` for one colleague.
    """

    def __init__(self, calendar_repository: CalendarRepository):
        self.calendar_repository = calendar_repository

    def execute(
        self,
        *,
        current_user_id: UUID,
        current_user_role: str,
        start: datetime,
        end: datetime,
        types: tuple[str, ...] | None = None,
        scope: str = "mine",
        owner_id: UUID | None = None,
    ) -> list[CalendarEventDTO]:
        if start is None or end is None:
            raise ValueError("Both start and end are required.")

        if end <= start:
            raise ValueError("End must be after start.")

        if end - start > MAX_RANGE:
            raise ValueError("The date range cannot exceed 62 days.")

        selected = tuple(types) if types else EVENT_TYPES
        invalid = [item for item in selected if item not in EVENT_TYPES]
        if invalid:
            raise ValueError(f"Unknown event type(s): {', '.join(invalid)}.")

        if scope not in {"mine", "team"}:
            raise ValueError("Scope must be 'mine' or 'team'.")

        can_view_team = current_user_role in TEAM_VIEW_ROLES

        if owner_id is not None and owner_id != current_user_id:
            if not can_view_team:
                raise PermissionError("You cannot view another user's calendar.")
            user_filter = owner_id
        elif scope == "team":
            if not can_view_team:
                raise PermissionError("You cannot view the team calendar.")
            user_filter = None
        else:
            user_filter = current_user_id

        fetchers = {
            "TASK": self.calendar_repository.get_tasks,
            "MEETING": self.calendar_repository.get_meetings,
            "CALL": self.calendar_repository.get_calls,
            "REMINDER": self.calendar_repository.get_reminders,
        }

        events: list[CalendarEventDTO] = []
        for event_type in selected:
            events.extend(
                fetchers[event_type](start=start, end=end, user_id=user_filter)
            )

        return sorted(events, key=_sort_key)


def _sort_key(event: CalendarEventDTO):
    # Dates (all-day tasks) sort at the start of their day, before timed items.
    start = event.start
    if isinstance(start, datetime):
        return (start.date().isoformat(), 1, start.isoformat(), event.title)
    return (start.isoformat(), 0, "", event.title)
