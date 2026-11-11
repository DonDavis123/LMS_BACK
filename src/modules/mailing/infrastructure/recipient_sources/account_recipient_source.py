from __future__ import annotations

from typing import Sequence
from uuid import UUID

from src.modules.mailing.application.dto.resolve_recipients import (
    FilterSpec,
    SourceRecord,
)
from src.modules.mailing.application.interfaces.record_readers import (
    AccountReaderPort,
    ContactReaderPort,
    ListUseCasePort,
)
from src.modules.mailing.domain.enums.mail_entity import MailEntity
from src.modules.mailing.domain.enums.record_type import RecordType

from .contact_recipient_source import contact_target
from .list_paging import read_all_matching


class AccountRecipientSource:
    """Accounts have no email: each one stands for its contacts.

    The contacts come from the contact repository's existing
    ``get_by_account_id_with_owner`` (company scoped, soft-deleted contacts
    excluded), one query per account.
    """

    entity = MailEntity.ACCOUNTS
    record_type = RecordType.ACCOUNT

    def __init__(
        self,
        list_use_case: ListUseCasePort,
        account_repository: AccountReaderPort,
        contact_repository: ContactReaderPort,
    ):
        self._list_use_case = list_use_case
        self._accounts = account_repository
        self._contacts = contact_repository

    def get_by_ids(self, ids: Sequence[UUID]) -> list[SourceRecord]:
        return [
            self._record(account.id, account.account_name)
            for account in self._accounts.get_many_by_ids(list(ids))
        ]

    def get_matching(
        self,
        search: str | None,
        filters: Sequence[FilterSpec],
        max_matches: int,
    ) -> list[SourceRecord]:
        rows = read_all_matching(self._list_use_case, search, filters, max_matches)
        return [self._record(row.id, row.account_name) for row in rows]

    def _record(self, account_id: UUID, account_name: str) -> SourceRecord:
        contacts = self._contacts.get_by_account_id_with_owner(account_id)
        return SourceRecord(
            record_id=account_id,
            record_type=RecordType.ACCOUNT,
            name=account_name,
            targets=tuple(
                contact_target(contact, account_name, source_account_id=account_id)
                for contact, _owner_name in contacts
            ),
        )
