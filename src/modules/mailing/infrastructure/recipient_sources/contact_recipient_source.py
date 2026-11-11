from __future__ import annotations

from typing import Mapping, Sequence
from uuid import UUID

from src.modules.mailing.application.dto.resolve_recipients import (
    FilterSpec,
    MailTarget,
    SourceRecord,
)
from src.modules.mailing.application.interfaces.record_readers import (
    AccountReaderPort,
    ContactLike,
    ContactReaderPort,
    ListUseCasePort,
)
from src.modules.mailing.domain.enums.mail_entity import MailEntity
from src.modules.mailing.domain.enums.record_type import RecordType

from .list_paging import read_all_matching


def contact_target(
    contact: ContactLike,
    account_name: str | None,
    source_account_id: UUID | None = None,
) -> MailTarget:
    return MailTarget(
        record_id=contact.id,
        record_type=RecordType.CONTACT,
        name=contact.name,
        email=contact.email,
        secondary_email=contact.secondary_email,
        email_opt_out=bool(contact.email_opt_out),
        account_name=account_name,
        source_account_id=source_account_id,
    )


def _record(target: MailTarget) -> SourceRecord:
    return SourceRecord(
        record_id=target.record_id,
        record_type=RecordType.CONTACT,
        name=target.name,
        targets=(target,),
    )


class ContactRecipientSource:
    """Contacts, by id or by the contact list's search and filters."""

    entity = MailEntity.CONTACTS
    record_type = RecordType.CONTACT

    def __init__(
        self,
        list_use_case: ListUseCasePort,
        contact_repository: ContactReaderPort,
        account_repository: AccountReaderPort,
    ):
        self._list_use_case = list_use_case
        self._contacts = contact_repository
        self._accounts = account_repository

    def get_by_ids(self, ids: Sequence[UUID]) -> list[SourceRecord]:
        contacts = list(self._contacts.get_many_by_ids(list(ids)))

        # One more query for all the account names (no query per contact).
        account_ids = list({c.account_id for c in contacts if c.account_id})
        account_names: Mapping[UUID, str] = (
            {a.id: a.account_name for a in self._accounts.get_many_by_ids(account_ids)}
            if account_ids
            else {}
        )

        return [
            _record(contact_target(contact, account_names.get(contact.account_id)))
            for contact in contacts
        ]

    def get_matching(
        self,
        search: str | None,
        filters: Sequence[FilterSpec],
        max_matches: int,
    ) -> list[SourceRecord]:
        rows = read_all_matching(self._list_use_case, search, filters, max_matches)
        return [
            _record(
                MailTarget(
                    record_id=row["id"],
                    record_type=RecordType.CONTACT,
                    name=row["name"],
                    email=row["email"],
                    secondary_email=row["secondary_email"],
                    email_opt_out=bool(row["email_opt_out"]),
                    account_name=row["account_name"],
                )
            )
            for row in rows
        ]
