from dataclasses import dataclass
from uuid import UUID


@dataclass
class LeadOwnerResponseDTO:
    id: UUID
    name: str
    email: str