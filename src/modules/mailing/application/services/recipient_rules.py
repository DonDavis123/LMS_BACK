"""Pure rules for resolving mail recipients: no Django, no I/O.

Whether an address is well formed is decided by a validator that is handed in
(``EmailValidator``); the production one wraps Django's ``validate_email``.
"""

from __future__ import annotations

from typing import Sequence, TypeVar

from src.modules.mailing.application.dto.limits import (
    MAX_BATCH_SIZE,
    MIN_BATCH_SIZE,
)
from src.modules.mailing.application.dto.resolve_recipients import MailTarget
from src.modules.mailing.application.interfaces.email_validator import (
    EmailValidator,
)
from src.modules.mailing.domain.entities.recipient import Recipient, SkippedRecord
from src.modules.mailing.domain.enums.email_kind import EmailKind
from src.modules.mailing.domain.enums.skip_reason import SkipReason

T = TypeVar("T")

def clean_email(value: str | None) -> str:
    """The address without surrounding blanks ('' when missing)."""
    return (value or "").strip()


def email_key(value: str | None) -> str:
    """The form in which addresses are compared and sent in a batch."""
    return clean_email(value).lower()


def check_email(value: str | None, is_valid: EmailValidator) -> SkipReason | None:
    """Why this address cannot be used, or ``None`` when it can."""
    address = clean_email(value)
    if not address:
        return SkipReason.NO_EMAIL
    if not is_valid(address):
        return SkipReason.INVALID_EMAIL
    return None


def validate_batch_size(batch_size: int) -> int:
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or not MIN_BATCH_SIZE <= batch_size <= MAX_BATCH_SIZE
    ):
        raise ValueError(
            f"batch_size must be a whole number between {MIN_BATCH_SIZE} "
            f"and {MAX_BATCH_SIZE}."
        )
    return batch_size


def unique_in_order(items: Sequence[T]) -> list[T]:
    """``items`` without repeats, first occurrence kept."""
    seen: set = set()
    result: list[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def chunk(items: Sequence[T], size: int) -> list[list[T]]:
    """Consecutive slices of at most ``size`` items (``[]`` for no items)."""
    if size < 1:
        raise ValueError("Chunk size must be at least 1.")
    return [list(items[start:start + size]) for start in range(0, len(items), size)]


class EmailRegistry:
    """Remembers the addresses already taken, case-insensitively."""

    def __init__(self) -> None:
        self._taken: set[str] = set()

    def claim(self, address: str) -> bool:
        """``True`` the first time an address is seen, ``False`` afterwards."""
        key = email_key(address)
        if key in self._taken:
            return False
        self._taken.add(key)
        return True


def resolve_target(
    target: MailTarget,
    include_secondary_email: bool,
    is_valid: EmailValidator,
    registry: EmailRegistry,
) -> tuple[list[Recipient], list[SkippedRecord]]:
    """Apply the mailing rules to one contact or lead.

    * opted out            -> OPTED_OUT (no address of the record is used)
    * no / malformed email -> NO_EMAIL / INVALID_EMAIL
    * address seen before  -> DUPLICATE_EMAIL (first one wins)
    * a valid secondary email, when asked for, is one more recipient. A
      missing or malformed secondary email is ignored; a duplicate is reported.
    """
    recipients: list[Recipient] = []
    skipped: list[SkippedRecord] = []

    def skip(reason: SkipReason) -> None:
        skipped.append(
            SkippedRecord(
                record_id=target.record_id,
                record_type=target.record_type,
                name=target.name,
                reason=reason,
            )
        )

    def accept(address: str, kind: EmailKind) -> None:
        if registry.claim(address):
            recipients.append(
                Recipient(
                    record_id=target.record_id,
                    record_type=target.record_type,
                    name=target.name,
                    email=address,
                    email_kind=kind,
                    account_name=target.account_name,
                    source_account_id=target.source_account_id,
                )
            )
        else:
            skip(SkipReason.DUPLICATE_EMAIL)

    if target.email_opt_out:
        skip(SkipReason.OPTED_OUT)
        return recipients, skipped

    problem = check_email(target.email, is_valid)
    if problem is None:
        accept(clean_email(target.email), EmailKind.PRIMARY)
    else:
        skip(problem)

    if include_secondary_email and check_email(target.secondary_email, is_valid) is None:
        accept(clean_email(target.secondary_email), EmailKind.SECONDARY)

    return recipients, skipped
