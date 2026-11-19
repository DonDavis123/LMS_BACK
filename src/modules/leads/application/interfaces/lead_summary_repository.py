from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.leads.domain.entities.lead_summary import LeadSummary


class LeadSummaryRepository(ABC):
    """Storage of the one current summary of each lead."""

    @abstractmethod
    def get_by_lead_id(self, lead_id: UUID) -> LeadSummary | None:
        pass

    @abstractmethod
    def replace_for_lead(self, summary: LeadSummary) -> LeadSummary:
        """Permanently delete the lead's previous summary (if any) and store
        ``summary`` in its place, in one transaction.

        Nothing of the old summary is kept: no history, no soft delete.
        """
        pass

    @abstractmethod
    def delete_by_lead_id(self, lead_id: UUID) -> int:
        """Permanently delete the lead's summary. Returns how many were removed."""
        pass
