from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.contacts.domain.entities.contact import Contact


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
    ) -> list[tuple[Contact, str | None, str | None]]:
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

    @abstractmethod
    def get_by_id_with_relations(
    self,
    contact_id: UUID,
) -> tuple[Contact, str | None, str | None] | None:
       pass