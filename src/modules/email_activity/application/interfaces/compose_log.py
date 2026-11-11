from abc import ABC, abstractmethod

from src.modules.email_activity.application.dto.log_email_compose import (
    ComposeEvent,
    ComposeTarget,
)


class ComposeLog(ABC):
    """Where compose events are stored and looked up (idempotency)."""

    @abstractmethod
    def find_logged(
        self,
        targets: list[ComposeTarget],
        client_ref: str,
    ) -> set[ComposeTarget]:
        """The ``targets`` that already have an event with this ``client_ref``,
        in ONE query."""
        pass

    @abstractmethod
    def record(self, events: list[ComposeEvent]) -> None:
        """Store the events (one per target)."""
        pass
