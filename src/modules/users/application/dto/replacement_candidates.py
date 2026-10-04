from dataclasses import dataclass
from uuid import UUID

from src.modules.users.domain.entities.role import UserRole


@dataclass(frozen=True)
class ReplacementCandidateDTO:
    id: UUID
    name: str
    email: str
    role: UserRole
