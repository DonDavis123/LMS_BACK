from __future__ import annotations

from typing import Protocol, Sequence
from uuid import UUID

from src.modules.mailing.application.dto.resolve_recipients import (
    FilterSpec,
    SourceRecord,
)
from src.modules.mailing.domain.enums.mail_entity import MailEntity
from src.modules.mailing.domain.enums.record_type import RecordType


class SelectionTooLargeError(ValueError):
    """The search/filters match more records than one mailing may hold."""


class RecipientSource(Protocol):
    """Where the records of one list (contacts, leads or accounts) come from.

    Implementations are scoped to the caller's company and never return
    soft-deleted records.
    """

    entity: MailEntity
    record_type: RecordType

    def get_by_ids(self, ids: Sequence[UUID]) -> list[SourceRecord]:
        """The records that exist for these ids, in any order. Unknown,
        soft-deleted and other-company ids are simply absent."""
        ...

    def get_matching(
        self,
        search: str | None,
        filters: Sequence[FilterSpec],
        max_matches: int,
    ) -> list[SourceRecord]:
        """Every record the list would show for this search and these filters
        (all pages, in list order).

        Raises ``ValueError`` for a bad filter and ``SelectionTooLargeError``
        when more than ``max_matches`` records match.
        """
        ...
