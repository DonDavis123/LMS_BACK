from __future__ import annotations

from uuid import UUID

from src.modules.mailing.application.dto.limits import (
    MAX_EXCLUDE_IDS,
    MAX_FILTER_MATCHES,
    MAX_IDS,
)
from src.modules.mailing.application.dto.resolve_recipients import (
    FilterSelection,
    IdsSelection,
    ResolveRecipientsCommand,
    ResolveRecipientsResult,
    SourceRecord,
)
from src.modules.mailing.application.interfaces.email_validator import (
    EmailValidator,
)
from src.modules.mailing.application.interfaces.recipient_source import (
    RecipientSource,
)
from src.modules.mailing.application.services.recipient_rules import (
    EmailRegistry,
    chunk,
    resolve_target,
    unique_in_order,
    validate_batch_size,
)
from src.modules.mailing.domain.entities.recipient import Recipient, SkippedRecord
from src.modules.mailing.domain.enums.record_type import RecordType
from src.modules.mailing.domain.enums.skip_reason import SkipReason


class ResolveMailRecipientsUseCase:
    """Turns a UI selection into recipients, skipped records and Bcc batches.

    The records come from a ``RecipientSource`` that is already scoped to the
    caller's company (for a filter selection it reads through the entity's own
    list use case, so search, filters and validation are those of the list).
    Everything else is decided here by pure rules.
    """

    def __init__(self, source: RecipientSource, is_valid_email: EmailValidator):
        self.source = source
        self.is_valid_email = is_valid_email

    def execute(self, command: ResolveRecipientsCommand) -> ResolveRecipientsResult:
        batch_size = validate_batch_size(command.batch_size)

        selection = command.selection
        if isinstance(selection, IdsSelection):
            steps, selected = self._steps_for_ids(selection)
        elif isinstance(selection, FilterSelection):
            steps, selected = self._steps_for_filter(selection)
        else:
            raise ValueError("selection mode is not supported.")

        registry = EmailRegistry()
        recipients: list[Recipient] = []
        skipped: list[SkippedRecord] = []

        for step in steps:
            if isinstance(step, SkippedRecord):
                skipped.append(step)
                continue
            new_recipients, new_skipped = self._resolve_record(
                step, command.include_secondary_email, registry
            )
            recipients.extend(new_recipients)
            skipped.extend(new_skipped)

        return ResolveRecipientsResult(
            entity=self.source.entity,
            selected=selected,
            recipients=recipients,
            skipped=skipped,
            batches=chunk([r.email_key for r in recipients], batch_size),
        )

    # -- selection -> ordered records (or NOT_FOUND entries) ------------------

    def _steps_for_ids(
        self, selection: IdsSelection
    ) -> tuple[list[SourceRecord | SkippedRecord], int]:
        if not selection.ids:
            raise ValueError("ids must contain at least one id.")
        if len(selection.ids) > MAX_IDS:
            raise ValueError(f"ids mode accepts at most {MAX_IDS} ids.")

        ids = unique_in_order(list(selection.ids))
        found = {record.record_id: record for record in self.source.get_by_ids(ids)}

        steps: list[SourceRecord | SkippedRecord] = []
        for record_id in ids:
            record = found.get(record_id)
            if record is None:
                steps.append(self._not_found(record_id))
            else:
                steps.append(record)
        return steps, len(ids)

    def _steps_for_filter(
        self, selection: FilterSelection
    ) -> tuple[list[SourceRecord | SkippedRecord], int]:
        if len(selection.exclude_ids) > MAX_EXCLUDE_IDS:
            raise ValueError(f"exclude_ids accepts at most {MAX_EXCLUDE_IDS} ids.")

        excluded = set(selection.exclude_ids)
        matches = self.source.get_matching(
            selection.search, selection.filters, MAX_FILTER_MATCHES
        )

        steps: list[SourceRecord | SkippedRecord] = []
        seen: set[UUID] = set()
        for record in matches:
            # A page can shift while it is read; never count a record twice.
            if record.record_id in excluded or record.record_id in seen:
                continue
            seen.add(record.record_id)
            steps.append(record)
        return steps, len(steps)

    def _not_found(self, record_id: UUID) -> SkippedRecord:
        return SkippedRecord(
            record_id=record_id,
            record_type=self.source.record_type,
            name="",
            reason=SkipReason.NOT_FOUND,
        )

    # -- record -> recipients -------------------------------------------------

    def _resolve_record(
        self,
        record: SourceRecord,
        include_secondary_email: bool,
        registry: EmailRegistry,
    ) -> tuple[list[Recipient], list[SkippedRecord]]:
        if record.record_type is RecordType.ACCOUNT and not record.targets:
            return [], [
                SkippedRecord(
                    record_id=record.record_id,
                    record_type=record.record_type,
                    name=record.name,
                    reason=SkipReason.NO_CONTACTS,
                )
            ]

        recipients: list[Recipient] = []
        skipped: list[SkippedRecord] = []
        for target in record.targets:
            new_recipients, new_skipped = resolve_target(
                target, include_secondary_email, self.is_valid_email, registry
            )
            recipients.extend(new_recipients)
            skipped.extend(new_skipped)
        return recipients, skipped
