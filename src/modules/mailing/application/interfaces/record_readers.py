"""What the recipient sources need from the other modules, as Protocols.

The real list use cases and repositories are handed in by
``presentation/api/dependencies``; nothing here imports those modules.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence
from uuid import UUID


class ListUseCasePort(Protocol):
    """A module's list use case: ``execute(ListQuery) -> PaginatedResult``."""

    def execute(self, query: Any) -> Any: ...


class ContactLike(Protocol):
    id: UUID
    account_id: UUID | None
    name: str
    email: str | None
    secondary_email: str | None
    email_opt_out: bool


class LeadLike(Protocol):
    id: UUID
    name: str
    email: str | None


class AccountLike(Protocol):
    id: UUID
    account_name: str


class ContactReaderPort(Protocol):
    def get_many_by_ids(self, ids: list[UUID]) -> Sequence[ContactLike]: ...

    def get_by_account_id_with_owner(
        self, account_id: UUID
    ) -> Sequence[tuple[ContactLike, str | None]]: ...


class LeadReaderPort(Protocol):
    def get_many_by_ids(self, ids: list[UUID]) -> Sequence[LeadLike]: ...


class AccountReaderPort(Protocol):
    def get_many_by_ids(self, ids: list[UUID]) -> Sequence[AccountLike]: ...
