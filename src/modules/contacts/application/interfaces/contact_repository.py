from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from src.modules.contacts.domain.entities.contact import Contact
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class ContactRepository(ABC):

    @abstractmethod
    def save(self, contact: Contact) -> Contact:
        pass

    @abstractmethod
    def get_by_id(self, contact_id: UUID) -> Contact | None:
        pass

    @abstractmethod
    def get_all_with_relations(
        self,
        query: ListQuery,
    ) -> PaginatedResult[
        tuple[
            Contact,
            str | None,
            str | None,
            date | None,
            str | None,
        ]
    ]:
        pass

    @abstractmethod
    def get_by_account_id_with_owner(
        self,
        account_id: UUID,
    ) -> list[tuple[Contact, str | None]]:
        pass

    @abstractmethod
    def find_conversion_matches(
        self,
        name: str,
        email: str | None,
        phone: str | None,
        mobile: str | None,
    ) -> list[Contact]:
        pass

    def find_for_import_matching(
        self,
        emails: set[str],
        phone_endings: set[str],
    ) -> list[Contact]:
        """Active contacts whose trimmed, lower-case email is in ``emails``
        (keys passed in that form), or whose phone or mobile ENDS WITH one of
        ``phone_endings`` (candidates only: the caller compares the last 10
        digits). Oldest first. One query for a whole import batch."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id_with_relations(
    self,
    contact_id: UUID,
) -> tuple[Contact, str | None, str | None] | None:
       pass

    @abstractmethod
    def unlink_account_contacts(self, account_id: UUID) -> None:
       pass


    @abstractmethod
    def transfer_ownership(
        self,
        from_user_id: UUID,
        to_user_id: UUID,
    ) -> int:
        """Reassign every Contact owned by ``from_user_id`` to ``to_user_id``."""
        pass


    @abstractmethod
    def count_by_owner_id(self, owner_id: UUID) -> int:
        pass
