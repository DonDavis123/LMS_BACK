from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from src.modules.email_activity.domain.enums.channel import EmailChannel
from src.modules.email_activity.domain.enums.record_type import RecordType

MAX_TARGETS = 50
MAX_SUBJECT_LENGTH = 200
MAX_MESSAGE_LENGTH = 500


@dataclass(frozen=True)
class ComposeTarget:
    record_type: RecordType
    record_id: UUID


@dataclass(frozen=True)
class LogEmailComposeCommand:
    """What the caller asked for. The actor comes from the authenticated user,
    never from the request body."""

    actor_id: UUID
    actor_name: str
    client_ref: UUID
    channel: EmailChannel
    targets: tuple[ComposeTarget, ...]
    subject: str | None = None
    batch_index: int | None = None
    batch_total: int | None = None


@dataclass(frozen=True)
class ComposeEvent:
    """One timeline event, for exactly one record."""

    target: ComposeTarget
    actor_id: UUID
    message: str
    metadata: dict


@dataclass(frozen=True)
class LogEmailComposeResult:
    logged: int
    already_logged: int
    not_found: tuple[ComposeTarget, ...] = field(default_factory=tuple)
