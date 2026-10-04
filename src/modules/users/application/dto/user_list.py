from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.users.domain.entities.role import UserRole


@dataclass(frozen=True)
class UserListDTO:
    id: UUID
    name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
