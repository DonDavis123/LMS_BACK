import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.modules.companies.domain.entities.platform_audit_action import (
    PlatformAuditAction,
)
from src.modules.users.domain.entities.user import User


@dataclass
class PlatformAuditLog:
    """What a platform admin did, to which company (and user), and when.

    Emails are snapshots. Never put secrets (passwords, tokens) in
    ``metadata``.
    """

    id: UUID
    action: PlatformAuditAction | str
    actor_id: UUID
    actor_email: str
    created_at: datetime
    company_id: UUID | None = None
    target_user_id: UUID | None = None
    target_email: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        action: PlatformAuditAction,
        actor: User,
        company_id: UUID | None = None,
        target: User | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "PlatformAuditLog":
        return cls(
            id=uuid.uuid4(),
            action=action,
            actor_id=actor.id,
            actor_email=actor.email,
            created_at=datetime.now(timezone.utc),
            company_id=company_id,
            target_user_id=target.id if target else None,
            target_email=target.email if target else "",
            metadata=dict(metadata or {}),
        )
