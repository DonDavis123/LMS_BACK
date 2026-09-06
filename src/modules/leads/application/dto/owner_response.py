from dataclasses import dataclass
from uuid import UUID


@dataclass
class OwnerResponseDTO:
    id: UUID
    name: str