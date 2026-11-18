from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from src.modules.deals.domain.enums.deal_stage import DealStage


@dataclass(frozen=True)
class DealForecastQuery:
    # IANA zone name that decides which calendar month "this month" is. The
    # presentation layer defaults it to the project's TIME_ZONE.
    timezone_name: str
    owner_id: UUID | None = None


@dataclass(frozen=True)
class StageForecastDTO:
    stage: DealStage
    count: int
    total_amount: Decimal
    weighted_amount: Decimal


@dataclass(frozen=True)
class MonthForecastDTO:
    # "YYYY-MM", or None for deals without an expected close date.
    month: str | None
    total_amount: Decimal
    weighted_amount: Decimal


@dataclass(frozen=True)
class DealForecastDTO:
    open_pipeline: Decimal
    weighted_forecast: Decimal
    won_this_month: Decimal
    lost_this_month: Decimal
    open_deal_count: int
    by_stage: list[StageForecastDTO] = field(default_factory=list)
    by_month: list[MonthForecastDTO] = field(default_factory=list)
