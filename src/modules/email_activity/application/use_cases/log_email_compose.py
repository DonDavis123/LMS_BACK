from __future__ import annotations

import unicodedata
from typing import Mapping

from src.modules.email_activity.application.dto.log_email_compose import (
    MAX_MESSAGE_LENGTH,
    MAX_SUBJECT_LENGTH,
    MAX_TARGETS,
    ComposeEvent,
    ComposeTarget,
    LogEmailComposeCommand,
    LogEmailComposeResult,
)
from src.modules.email_activity.application.interfaces.compose_log import ComposeLog
from src.modules.email_activity.application.interfaces.record_lookup import (
    RecordLookup,
)
from src.modules.email_activity.application.interfaces.transaction import (
    TransactionPort,
)
from src.modules.email_activity.domain.enums.channel import EmailChannel
from src.modules.email_activity.domain.enums.record_type import RecordType

_ZERO_WIDTH_JOINER = "\u200d"


def normalize_subject(subject: str | None) -> str | None:
    """Trimmed, control characters replaced by a space (a NUL cannot be stored
    in the JSON column), cut to ``MAX_SUBJECT_LENGTH`` characters without
    leaving a dangling joiner or space at the cut. Empty becomes ``None``."""
    if subject is None:
        return None
    cleaned = "".join(
        " " if unicodedata.category(char) == "Cc" else char for char in str(subject)
    ).strip()
    if len(cleaned) > MAX_SUBJECT_LENGTH:
        cleaned = cleaned[:MAX_SUBJECT_LENGTH].rstrip().rstrip(_ZERO_WIDTH_JOINER).rstrip()
    return cleaned or None


def _clean_email(email: str | None) -> str | None:
    return (email or "").strip() or None


class LogEmailComposeUseCase:
    """Writes "email opened in Gmail" to the timeline of each target record.

    The server never sends the email and cannot know whether the user sent
    it, so the wording only says it was *opened*. One event is written PER
    target (a record's timeline never shows the other recipients), and the
    same ``client_ref`` never creates a second event for the same target.
    """

    def __init__(
        self,
        lookups: Mapping[RecordType, RecordLookup],
        compose_log: ComposeLog,
        transaction_manager: TransactionPort,
    ):
        self.lookups = lookups
        self.compose_log = compose_log
        self.transaction_manager = transaction_manager

    def execute(self, command: LogEmailComposeCommand) -> LogEmailComposeResult:
        if command.channel not in set(EmailChannel):
            raise ValueError("channel is not supported.")
        self._validate_batch(command.batch_index, command.batch_total)
        targets = self._unique_targets(command.targets)
        subject = normalize_subject(command.subject)

        emails = self._find_emails(targets)
        found = [t for t in targets if t.record_id in emails[t.record_type]]
        not_found = tuple(t for t in targets if t.record_id not in emails[t.record_type])

        if not found:
            return LogEmailComposeResult(0, 0, not_found)

        client_ref = str(command.client_ref)
        message = f"Email opened in Gmail by {command.actor_name}"[:MAX_MESSAGE_LENGTH]

        def write() -> tuple[int, int]:
            done = self.compose_log.find_logged(found, client_ref)
            new = [t for t in found if t not in done]
            if new:
                self.compose_log.record(
                    [
                        ComposeEvent(
                            target=target,
                            actor_id=command.actor_id,
                            message=message,
                            metadata={
                                "client_ref": client_ref,
                                "channel": command.channel.value,
                                "subject": subject,
                                "recipient_email": _clean_email(
                                    emails[target.record_type][target.record_id]
                                ),
                                "batch_index": command.batch_index,
                                "batch_total": command.batch_total,
                            },
                        )
                        for target in new
                    ]
                )
            return len(new), len(found) - len(new)

        logged, already_logged = self.transaction_manager.execute(write)
        return LogEmailComposeResult(logged, already_logged, not_found)

    @staticmethod
    def _validate_batch(batch_index: int | None, batch_total: int | None) -> None:
        for name, value in (("batch_index", batch_index), ("batch_total", batch_total)):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 1
            ):
                raise ValueError(f"{name} must be a positive whole number.")
        if batch_index is not None and batch_total is not None and batch_index > batch_total:
            raise ValueError("batch_index cannot be greater than batch_total.")

    @staticmethod
    def _unique_targets(targets: tuple[ComposeTarget, ...]) -> list[ComposeTarget]:
        if not targets:
            raise ValueError("targets must contain at least one target.")
        if len(targets) > MAX_TARGETS:
            raise ValueError(f"targets cannot contain more than {MAX_TARGETS} entries.")
        # Duplicates are collapsed; the first occurrence keeps its place.
        return list(dict.fromkeys(targets))

    def _find_emails(
        self, targets: list[ComposeTarget]
    ) -> dict[RecordType, dict]:
        emails: dict[RecordType, dict] = {}
        for record_type in RecordType:
            ids = [t.record_id for t in targets if t.record_type is record_type]
            if not ids:
                emails[record_type] = {}
                continue
            lookup = self.lookups.get(record_type)
            if lookup is None:
                raise ValueError("record_type is not supported.")
            emails[record_type] = lookup.find_emails(ids)
        return emails
