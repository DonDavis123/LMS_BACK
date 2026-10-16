from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class DashboardWindow:
    """Calendar-day window the stats are computed for (in the caller's time zone).

    ``from_at`` .. ``to_at`` is the selected range (``to_at`` exclusive), and
    ``previous_from_at`` .. ``from_at`` is the same-length window before it.
    """

    days: tuple[date, ...]
    previous_from_at: datetime
    from_at: datetime
    to_at: datetime
    timezone_name: str


@dataclass(frozen=True)
class LeadCountsDTO:
    total: int
    new_in_range: int
    new_previous_range: int
    converted: int


@dataclass(frozen=True)
class LeadStatsDTO:
    counts: LeadCountsDTO
    by_status: list[tuple[str, int]]
    by_source: list[tuple[str, int]]
    created_per_day: dict[date, int]


@dataclass(frozen=True)
class DashboardStatsDTO:
    range_days: int
    generated_at: datetime
    total: int
    new_in_range: int
    new_previous_range: int
    converted: int
    by_status: list[tuple[str, int]]
    by_source: list[tuple[str, int]]
    created_per_day: list[tuple[date, int]]
