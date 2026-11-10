from dataclasses import dataclass
from uuid import UUID

from src.modules.users.domain.entities.role import UserRole

_UNSET = object()


@dataclass(frozen=True)
class UpdateUserDTO:
    user_id: UUID
    name: str | None = None
    email: str | None = None
    role: UserRole | None = None
    # _UNSET = leave unchanged, None = clear.
    google_email: str | None | object = _UNSET
