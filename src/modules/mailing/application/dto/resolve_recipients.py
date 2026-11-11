from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from src.modules.mailing.application.dto.limits import DEFAULT_BATCH_SIZE
from src.modules.mailing.domain.entities.recipient import Recipient, SkippedRecord
from src.modules.mailing.domain.enums.mail_entity import MailEntity
from src.modules.mailing.domain.enums.record_type import RecordType


@dataclass(frozen=True)
class FilterSpec:
    """One ``{"field", "operator", "value"}`` condition of the list screen."""

    field: str
    operator: str
    value: Any


@dataclass(frozen=True)
class IdsSelection:
    ids: tuple[UUID, ...]


@dataclass(frozen=True)
class FilterSelection:
    """Everything the list shows for ``search`` and ``filters``, except
    ``exclude_ids``."""

    search: str | None = None
    filters: tuple[FilterSpec, ...] = ()
    exclude_ids: tuple[UUID, ...] = ()


Selection = IdsSelection | FilterSelection


@dataclass(frozen=True)
class ResolveRecipientsCommand:
    selection: Selection
    include_secondary_email: bool = False
    batch_size: int = DEFAULT_BATCH_SIZE


@dataclass(frozen=True)
class MailTarget:
    """A contact or lead as the rules need it (never an account)."""

    record_id: UUID
    record_type: RecordType
    name: str
    email: str | None
    secondary_email: str | None = None
    email_opt_out: bool = False
    account_name: str | None = None
    source_account_id: UUID | None = None


@dataclass(frozen=True)
class SourceRecord:
    """One selected record and the contacts/leads that stand for it.

    A contact or a lead has itself as its only target. An account has its
    contacts (possibly none).
    """

    record_id: UUID
    record_type: RecordType
    name: str
    targets: tuple[MailTarget, ...]


@dataclass(frozen=True)
class ResolveRecipientsResult:
    entity: MailEntity
    selected: int
    recipients: list[Recipient] = field(default_factory=list)
    skipped: list[SkippedRecord] = field(default_factory=list)
    batches: list[list[str]] = field(default_factory=list)
