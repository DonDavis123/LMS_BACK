from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.modules.dashboard.application.dto.dashboard_stats import (
    DashboardStatsDTO,
    DashboardWindow,
)
from src.modules.dashboard.application.interfaces.dashboard_repository import (
    DashboardRepository,
)

MIN_RANGE_DAYS = 1
MAX_RANGE_DAYS = 365


def resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError(f"Unknown time zone '{name}'.")


def build_window(range_days: int, tz: ZoneInfo, now: datetime) -> DashboardWindow:
    """Same day boundaries the frontend used: ``range_days`` calendar days ending today."""
    today = now.astimezone(tz).date()
    first_day = today - timedelta(days=range_days - 1)

    def start_of(day: date) -> datetime:
        # Local midnight, so a 23/25-hour DST day is still one calendar day.
        return datetime.combine(day, time.min, tzinfo=tz)

    return DashboardWindow(
        days=tuple(first_day + timedelta(days=offset) for offset in range(range_days)),
        previous_from_at=start_of(first_day - timedelta(days=range_days)),
        from_at=start_of(first_day),
        to_at=start_of(today + timedelta(days=1)),
        timezone_name=str(tz),
    )


class GetDashboardStatsUseCase:

    def __init__(self, dashboard_repository: DashboardRepository):
        self.dashboard_repository = dashboard_repository

    def execute(
        self,
        range_days: int,
        timezone_name: str,
        now: datetime | None = None,
    ) -> DashboardStatsDTO:
        if not MIN_RANGE_DAYS <= range_days <= MAX_RANGE_DAYS:
            raise ValueError(
                f"Range must be between {MIN_RANGE_DAYS} and {MAX_RANGE_DAYS} days."
            )

        now = now or datetime.now(dt_timezone.utc)
        window = build_window(range_days, resolve_timezone(timezone_name), now)
        stats = self.dashboard_repository.get_lead_stats(window)

        return DashboardStatsDTO(
            range_days=range_days,
            generated_at=now,
            total=stats.counts.total,
            new_in_range=stats.counts.new_in_range,
            new_previous_range=stats.counts.new_previous_range,
            converted=stats.counts.converted,
            by_status=stats.by_status,
            by_source=stats.by_source,
            # Every day of the window is present, empty days as 0.
            created_per_day=[(day, stats.created_per_day.get(day, 0)) for day in window.days],
        )
