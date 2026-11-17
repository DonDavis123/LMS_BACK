from abc import ABC, abstractmethod

from src.modules.leads.application.dto.lead_summary import LeadSummaryResult


class LeadSummaryError(Exception):
    """The summary service failed for this lead.

    ``user_message`` is safe to show to the end user (no keys, no raw provider
    payloads); the technical detail goes to the server log.
    """

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class LeadSummaryUnavailableError(Exception):
    """Lead summaries are not set up on this server (for example no API key)."""


class LeadSummaryGenerator(ABC):
    """Turns the written history of a lead into a short summary."""

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def generate(self, dossier: str) -> LeadSummaryResult:
        """``dossier`` is the plain-text history built by ``build_lead_dossier``.

        Raises ``LeadSummaryError`` when the summary could not be produced.
        """
        pass
