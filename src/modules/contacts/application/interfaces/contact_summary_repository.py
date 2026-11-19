from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.contacts.domain.entities.contact_summary import ContactSummary


class ContactSummaryRepository(ABC):
    """Storage of the one current summary of each contact."""

    @abstractmethod
    def get_by_contact_id(self, contact_id: UUID) -> ContactSummary | None:
        pass

    @abstractmethod
    def replace_for_contact(self, summary: ContactSummary) -> ContactSummary:
        """Permanently delete the contact's previous summary (if any) and store
        ``summary`` in its place, in one transaction.

        Nothing of the old summary is kept: no history, no soft delete.
        """
        pass

    @abstractmethod
    def delete_by_contact_id(self, contact_id: UUID) -> int:
        """Permanently delete the contact's summary. Returns how many were removed."""
        pass
