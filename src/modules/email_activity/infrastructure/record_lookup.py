from __future__ import annotations

from typing import Any, Protocol, Sequence
from uuid import UUID

from src.modules.email_activity.application.interfaces.record_lookup import (
    RecordLookup,
)


class RecordReader(Protocol):
    """What the lead and contact repositories offer: the repository's
    company's non-deleted records with these ids, in ONE query."""

    def get_many_by_ids(self, ids: list[UUID]) -> Sequence[Any]: ...


class RepositoryRecordLookup(RecordLookup):
    """``RecordLookup`` on top of an existing lead or contact repository.

    The repository is already scoped to the caller's company and hides
    soft-deleted rows, so records of other companies or deleted records are
    just missing from the result.
    """

    def __init__(self, repository: RecordReader):
        self.repository = repository

    def find_emails(self, ids: list[UUID]) -> dict[UUID, str | None]:
        return {
            record.id: record.email
            for record in self.repository.get_many_by_ids(list(ids))
        }
