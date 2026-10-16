from datetime import date, datetime, timezone
from unittest import TestCase

from src.modules.dashboard.application.dto.dashboard_stats import (
    LeadCountsDTO,
    LeadStatsDTO,
)
from src.modules.dashboard.application.interfaces.dashboard_repository import (
    DashboardRepository,
)
from src.modules.dashboard.application.use_cases.get_dashboard_stats import (
    GetDashboardStatsUseCase,
)


class FakeRepository(DashboardRepository):

    def __init__(self, per_day=None):
        self.window = None
        self.per_day = per_day or {}

    def get_lead_stats(self, window):
        self.window = window
        return LeadStatsDTO(
            counts=LeadCountsDTO(total=6, new_in_range=6, new_previous_range=0, converted=1),
            by_status=[("Contacted", 6)],
            by_source=[("Cold Call", 6)],
            created_per_day=self.per_day,
        )


# 2026-10-16 12:00 in Asia/Kolkata
NOW = datetime(2026, 10, 16, 6, 30, tzinfo=timezone.utc)


class GetDashboardStatsUseCaseTests(TestCase):

    def test_every_day_of_the_range_is_present_and_empty_days_are_zero(self):
        repo = FakeRepository({date(2026, 10, 4): 2})
        result = GetDashboardStatsUseCase(repo).execute(30, "Asia/Kolkata", now=NOW)

        days = [day for day, _ in result.created_per_day]
        self.assertEqual(len(days), 30)
        self.assertEqual(days[0], date(2026, 9, 17))
        self.assertEqual(days[-1], date(2026, 10, 16))
        self.assertEqual(dict(result.created_per_day)[date(2026, 10, 4)], 2)
        self.assertEqual(sum(count for _, count in result.created_per_day), 2)

    def test_window_uses_the_callers_calendar_days(self):
        repo = FakeRepository()
        GetDashboardStatsUseCase(repo).execute(7, "Asia/Kolkata", now=NOW)

        window = repo.window
        self.assertEqual(window.from_at.isoformat(), "2026-10-10T00:00:00+05:30")
        self.assertEqual(window.to_at.isoformat(), "2026-10-17T00:00:00+05:30")
        self.assertEqual(window.previous_from_at.isoformat(), "2026-10-03T00:00:00+05:30")

    def test_today_follows_the_time_zone_not_utc(self):
        late_utc = datetime(2026, 10, 16, 20, 0, tzinfo=timezone.utc)  # already 17 Oct in Kolkata
        repo = FakeRepository()
        result = GetDashboardStatsUseCase(repo).execute(7, "Asia/Kolkata", now=late_utc)
        self.assertEqual(result.created_per_day[-1][0], date(2026, 10, 17))

    def test_rejects_bad_range_and_unknown_time_zone(self):
        use_case = GetDashboardStatsUseCase(FakeRepository())
        with self.assertRaises(ValueError):
            use_case.execute(0, "Asia/Kolkata", now=NOW)
        with self.assertRaises(ValueError):
            use_case.execute(366, "Asia/Kolkata", now=NOW)
        with self.assertRaises(ValueError):
            use_case.execute(30, "Not/AZone", now=NOW)
