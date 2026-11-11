from __future__ import annotations

from typing import Sequence
from uuid import UUID

from src.modules.mailing.application.dto.resolve_recipients import (
    FilterSpec,
    MailTarget,
    SourceRecord,
)
from src.modules.mailing.application.interfaces.record_readers import (
    LeadReaderPort,
    ListUseCasePort,
)
from src.modules.mailing.domain.enums.mail_entity import MailEntity
from src.modules.mailing.domain.enums.record_type import RecordType

from .list_paging import read_all_matching


def _record(record_id: UUID, name: str, email: str | None) -> SourceRecord:
    # Leads have no opt-out flag and no secondary email.
    return SourceRecord(
        record_id=record_id,
        record_type=RecordType.LEAD,
        name=name,
        targets=(
            MailTarget(
                record_id=record_id,
                record_type=RecordType.LEAD,
                name=name,
                email=email,
            ),
        ),
    )


class LeadRecipientSource:
    """Leads, by id or by the lead list's search and filters."""

    entity = MailEntity.LEADS
    record_type = RecordType.LEAD

    def __init__(
        self,
        list_use_case: ListUseCasePort,
        lead_repository: LeadReaderPort,
    ):
        self._list_use_case = list_use_case
        self._leads = lead_repository

    def get_by_ids(self, ids: Sequence[UUID]) -> list[SourceRecord]:
        return [
            _record(lead.id, lead.name, lead.email)
            for lead in self._leads.get_many_by_ids(list(ids))
        ]

    def get_matching(
        self,
        search: str | None,
        filters: Sequence[FilterSpec],
        max_matches: int,
    ) -> list[SourceRecord]:
        rows = read_all_matching(self._list_use_case, search, filters, max_matches)
        return [_record(row.id, row.name, row.email) for row in rows]
