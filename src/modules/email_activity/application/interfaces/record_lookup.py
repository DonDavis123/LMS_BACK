from abc import ABC, abstractmethod
from uuid import UUID


class RecordLookup(ABC):
    """Finds the active records (of one record type) of the caller's company."""

    @abstractmethod
    def find_emails(self, ids: list[UUID]) -> dict[UUID, str | None]:
        """``{id: current email or None}`` for the ids that exist, are not
        soft-deleted and belong to the caller's company, in ONE query. Every
        other id is simply absent from the result."""
        pass
