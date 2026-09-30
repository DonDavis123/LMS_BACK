from dataclasses import dataclass
from uuid import UUID

from src.modules.users.domain.entities.role import UserRole


@dataclass(frozen=True)
class UpdateUserDTO:
    user_id: UUID
    name: str | None = None
    email: str | None = None
    role: UserRole | None = None
