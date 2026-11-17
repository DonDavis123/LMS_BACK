from dataclasses import dataclass
from uuid import UUID

from src.modules.deals.domain.enums.deal_stage import DealStage


@dataclass
class MoveDealStageDTO:
    deal_id: UUID
    stage: DealStage
    # None means the caller did not send one (use the stage default).
    probability: int | None = None
    lost_reason: str | None = None
