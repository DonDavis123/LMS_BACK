from abc import ABC, abstractmethod

from src.modules.contacts.application.dto.contact_summary import ContactSummaryResult


class ContactSummaryError(Exception):
    """The summary service failed for this contact.

    ``user_message`` is safe to show to the end user (no keys, no raw provider
    payloads); the technical detail goes to the server log.
    """

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class ContactSummaryUnavailableError(Exception):
    """Contact summaries are not set up on this server (for example no API key)."""


class ContactSummaryGenerator(ABC):
    """Turns the written history of a contact into a short summary."""

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def generate(self, dossier: str) -> ContactSummaryResult:
        """``dossier`` is the plain-text history built by ``build_contact_dossier``.

        Raises ``ContactSummaryError`` when the summary could not be produced.
        """
        pass
