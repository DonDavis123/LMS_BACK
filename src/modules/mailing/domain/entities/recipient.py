from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.modules.mailing.domain.enums.email_kind import EmailKind
from src.modules.mailing.domain.enums.record_type import RecordType
from src.modules.mailing.domain.enums.skip_reason import SkipReason


@dataclass(frozen=True)
class Recipient:
    """One address that will receive the mail."""

    record_id: UUID
    record_type: RecordType          # CONTACT or LEAD
    name: str
    email: str
    email_kind: EmailKind
    account_name: str | None = None
    source_account_id: UUID | None = None  # set when reached through an account

    @property
    def email_key(self) -> str:
        """The address as compared for duplicates and used in a batch."""
        return self.email.strip().lower()


@dataclass(frozen=True)
class SkippedRecord:
    """A selected record (or one of its addresses) that gets no mail."""

    record_id: UUID
    record_type: RecordType
    name: str
    reason: SkipReason
