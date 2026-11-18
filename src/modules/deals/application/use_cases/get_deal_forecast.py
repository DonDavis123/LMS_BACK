from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.modules.dashboard.application.use_cases.get_dashboard_stats import (
    resolve_timezone,
)
from src.modules.deals.application.dto.deal_forecast import (
    DealForecastDTO,
    DealForecastQuery,
)
from src.modules.deals.application.interfaces.deal_repository import DealRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def month_bounds(now: datetime, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Local midnight at the start of the current calendar month in ``tz`` and
    at the start of the next one (``[start, end)``), as aware datetimes."""
    local = now.astimezone(tz)
    start = datetime(local.year, local.month, 1, tzinfo=tz)

    if local.month == 12:
        end = datetime(local.year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(local.year, local.month + 1, 1, tzinfo=tz)

    return start, end


class GetDealForecastUseCase:

    def __init__(self, deal_repository: DealRepository):
        self.deal_repository = deal_repository

    def execute(
        self,
        query: DealForecastQuery,
        now: datetime | None = None,
    ) -> DealForecastDTO:
        # Same handling as the dashboard: an unknown zone is a ValueError.
        tz = resolve_timezone(query.timezone_name)

        month_start, month_end = month_bounds(now or _utcnow(), tz)

        return self.deal_repository.get_forecast(
            query.owner_id,
            month_start,
            month_end,
        )
