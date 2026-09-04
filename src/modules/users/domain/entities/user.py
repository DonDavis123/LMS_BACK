from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.users.domain.entities.role import UserRole


@dataclass
class User:
    id: UUID
    name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime