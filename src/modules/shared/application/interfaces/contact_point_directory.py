from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from src.modules.shared.application.dto.contact_point_match import (
    ContactPointMatch,
)


class ContactPointDirectory(ABC):
    """Looks up emails / phone numbers across leads, contacts and accounts
    of one company."""

    @abstractmethod
    def find_matches(
        self,
        *,
        emails: Sequence[str],
        phones: Sequence[str],
        exclude: tuple[str, UUID] | None = None,
    ) -> list[ContactPointMatch]:
        """Records already using any of the values. ``exclude`` is a
        ``(record_type, record_id)`` pair that is never reported (the record
        being edited)."""
