import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .user import User
from .user_audit_action import UserAuditAction


@dataclass
class UserAuditLog:
    """Who did what to which user, and when.

    Actor and target emails are snapshots so the entry stays readable even
    if the user is later renamed or retired. Never put secrets (passwords,
    tokens) in ``metadata``.
    """

    id: UUID
    action: UserAuditAction
    actor_id: UUID
    actor_email: str
    target_user_id: UUID
    target_email: str
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        action: UserAuditAction,
        actor: User,
        target: User,
        metadata: dict[str, Any] | None = None,
    ) -> "UserAuditLog":
        return cls(
            id=uuid.uuid4(),
            action=action,
            actor_id=actor.id,
            actor_email=actor.email,
            target_user_id=target.id,
            target_email=target.email,
            created_at=datetime.now(timezone.utc),
            metadata=dict(metadata or {}),
        )
