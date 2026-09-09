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
    def get_all(self) -> list[Contact]:
        pass