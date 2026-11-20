from abc import ABC, abstractmethod

from src.modules.dashboard.application.dto.daily_briefing import DailyBriefingResult


class DailyBriefingError(Exception):
    """The briefing service failed.

    ``user_message`` is safe to show to the end user (no keys, no raw provider
    payloads); the technical detail goes to the server log.
    """

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class DailyBriefingUnavailableError(Exception):
    """The daily briefing is not set up on this server (for example no API key)."""


class DailyBriefingGenerator(ABC):
    """Turns a user's open tasks and meetings into a prioritised plan for today."""

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def generate(self, dossier: str) -> DailyBriefingResult:
        """``dossier`` is the plain-text work list built by ``build_daily_briefing_dossier``.

        Raises ``DailyBriefingError`` when the plan could not be produced.
        """
        pass
