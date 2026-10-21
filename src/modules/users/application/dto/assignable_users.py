from dataclasses import dataclass
from uuid import UUID


@dataclass
class AssignableUserResponseDTO:
    id: UUID
    name: str
    email: str
    role: str
