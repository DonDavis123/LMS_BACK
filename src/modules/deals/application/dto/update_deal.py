from dataclasses import dataclass
from uuid import UUID


@dataclass
class UpdateDealDTO:
    deal_id: UUID
    fields: dict[str, object]
