from abc import ABC, abstractmethod

from src.modules.accounts.application.dto.account_summary import AccountSummaryResult


class AccountSummaryError(Exception):
    """The summary service failed for this account.

    ``user_message`` is safe to show to the end user (no keys, no raw provider
    payloads); the technical detail goes to the server log.
    """

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class AccountSummaryUnavailableError(Exception):
    """Account summaries are not set up on this server (for example no API key)."""


class AccountSummaryGenerator(ABC):
    """Turns the written history of an account into a short summary."""

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def generate(self, dossier: str) -> AccountSummaryResult:
        """``dossier`` is the plain-text history built by ``build_account_dossier``.

        Raises ``AccountSummaryError`` when the summary could not be produced.
        """
        pass
