from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from src.modules.deals.domain.enums.deal_stage import DealStage


@dataclass(frozen=True)
class DealBoardQuery:
    owner_id: UUID | None = None
    expected_close_from: date | None = None
    expected_close_to: date | None = None
    search: str | None = None
    # Only used for the Won and Lost columns.
    closed_within_days: int = 30


@dataclass(frozen=True)
class DealCardDTO:
    """One card on the board: a deal with its display names."""

    id: UUID
    name: str
    amount: Decimal
    expected_close_date: date | None
    probability: int
    owner_id: UUID
    owner_name: str | None
    account_id: UUID | None
    account_name: str | None
    contact_id: UUID | None
    contact_name: str | None


@dataclass(frozen=True)
class DealBoardColumnDTO:
    """One stage column. ``count`` and the amounts cover every matching deal;
    ``deals`` holds at most the card limit of them."""

    stage: DealStage
    default_probability: int
    count: int
    total_amount: Decimal
    weighted_amount: Decimal
    has_more: bool
    deals: list[DealCardDTO] = field(default_factory=list)
