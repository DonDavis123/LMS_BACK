from uuid import UUID

from src.modules.contacts.application.dto.contact_summary import ContactSummaryResponseDTO
from src.modules.contacts.application.interfaces.contact_repository import ContactRepository
from src.modules.contacts.application.interfaces.contact_summary_repository import (
    ContactSummaryRepository,
)


class GetContactSummaryUseCase:
    """Reads the stored summary of a contact. Never calls the model."""

    def __init__(
        self,
        contact_repository: ContactRepository,
        summary_repository: ContactSummaryRepository,
    ):
        self.contact_repository = contact_repository
        self.summary_repository = summary_repository

    def execute(self, contact_id: UUID) -> ContactSummaryResponseDTO | None:
        """The stored summary, or ``None`` when none was generated yet."""
        contact = self.contact_repository.get_by_id(contact_id)

        if contact is None or contact.is_deleted:
            raise ValueError("Contact not found.")

        summary = self.summary_repository.get_by_contact_id(contact.id)

        if summary is None:
            return None

        return ContactSummaryResponseDTO.from_entity(summary)
