from datetime import date, datetime, timedelta, timezone
from unittest import TestCase
from uuid import uuid4

from src.modules.calendar.application.dto.calendar_event import CalendarEventDTO
from src.modules.calendar.application.interfaces.calendar_repository import (
    CalendarRepository,
)
from src.modules.calendar.application.use_cases.get_calendar_events import (
    GetCalendarEventsUseCase,
)


def _event(event_type, start, title="x", all_day=False):
    return CalendarEventDTO(
        id=uuid4(),
        type=event_type,
        title=title,
        start=start,
        end=None,
        all_day=all_day,
        status=None,
        owner_id=None,
        owner_name=None,
    )


class FakeCalendarRepository(CalendarRepository):

    def __init__(self):
        self.user_ids = []
        self.nov_1 = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)

    def get_tasks(self, *, start, end, user_id):
        self.user_ids.append(user_id)
        return [_event("TASK", date(2026, 11, 1), "task", all_day=True)]

    def get_meetings(self, *, start, end, user_id):
        self.user_ids.append(user_id)
        return [_event("MEETING", self.nov_1, "meeting")]

    def get_calls(self, *, start, end, user_id):
        self.user_ids.append(user_id)
        return [_event("CALL", self.nov_1 - timedelta(hours=2), "call")]

    def get_reminders(self, *, start, end, user_id):
        self.user_ids.append(user_id)
        return [_event("REMINDER", self.nov_1 + timedelta(hours=1), "reminder")]


class GetCalendarEventsTests(TestCase):

    def setUp(self):
        self.repo = FakeCalendarRepository()
        self.use_case = GetCalendarEventsUseCase(self.repo)
        self.user_id = uuid4()
        self.start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.end = datetime(2026, 12, 1, tzinfo=timezone.utc)

    def run_case(self, **overrides):
        kwargs = dict(
            current_user_id=self.user_id,
            current_user_role="SALES_EXECUTIVE",
            start=self.start,
            end=self.end,
        )
        kwargs.update(overrides)
        return self.use_case.execute(**kwargs)

    def test_returns_all_types_sorted_with_all_day_first(self):
        events = self.run_case()

        self.assertEqual(
            [event.title for event in events],
            ["task", "call", "meeting", "reminder"],
        )

    def test_defaults_to_the_current_users_items(self):
        self.run_case()

        self.assertEqual(set(self.repo.user_ids), {self.user_id})

    def test_filters_by_type(self):
        events = self.run_case(types=("CALL",))

        self.assertEqual([event.type for event in events], ["CALL"])

    def test_unknown_type_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_case(types=("BOGUS",))

    def test_manager_can_view_team(self):
        self.run_case(current_user_role="SALES_MANAGER", scope="team")

        self.assertEqual(set(self.repo.user_ids), {None})

    def test_executive_cannot_view_team_or_other_users(self):
        with self.assertRaises(PermissionError):
            self.run_case(scope="team")

        with self.assertRaises(PermissionError):
            self.run_case(owner_id=uuid4())

    def test_manager_can_view_one_colleague(self):
        colleague = uuid4()

        self.run_case(current_user_role="ADMIN", owner_id=colleague)

        self.assertEqual(set(self.repo.user_ids), {colleague})

    def test_range_is_validated(self):
        with self.assertRaises(ValueError):
            self.run_case(end=self.start)

        with self.assertRaises(ValueError):
            self.run_case(end=self.start + timedelta(days=90))
