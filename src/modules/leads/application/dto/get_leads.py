from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .owner_response import OwnerResponseDTO


@dataclass
class LeadResponseDTO:
    id: UUID
    name: str
    company_name: str
    email: str | None
    mobile_number: str
    lead_source: str
    owner: OwnerResponseDTO
    lead_status:str
    created_at: datetime
    updated_at: datetime