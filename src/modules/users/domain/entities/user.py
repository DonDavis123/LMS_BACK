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
    deleted_at: datetime | None = None
    company_id: UUID | None = None
    google_email: str | None = None

    @property
    def mail_account_email(self) -> str:
        return self.google_email or self.email

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
