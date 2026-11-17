from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from src.modules.deals.domain.enums.deal_stage import DealStage


@dataclass
class CreateDealDTO:
    name: str
    owner_id: UUID
    created_by_id: UUID
    amount: Decimal = Decimal("0")
    expected_close_date: date | None = None
    stage: DealStage = DealStage.NEW
    # None means "use the stage default".
    probability: int | None = None
    account_id: UUID | None = None
    contact_id: UUID | None = None
    source_lead_id: UUID | None = None
    lead_source: str | None = None
    description: str | None = None
    lost_reason: str | None = None
