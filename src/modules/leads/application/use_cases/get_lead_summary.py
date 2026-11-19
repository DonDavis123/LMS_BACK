from uuid import UUID

from src.modules.leads.application.dto.lead_summary import LeadSummaryResponseDTO
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.application.interfaces.lead_summary_repository import (
    LeadSummaryRepository,
)


class GetLeadSummaryUseCase:
    """Reads the stored summary of a lead. Never calls the model."""

    def __init__(
        self,
        lead_repository: LeadRepository,
        summary_repository: LeadSummaryRepository,
    ):
        self.lead_repository = lead_repository
        self.summary_repository = summary_repository

    def execute(self, lead_id: UUID) -> LeadSummaryResponseDTO | None:
        """The stored summary, or ``None`` when none was generated yet."""
        lead = self.lead_repository.get_by_id(lead_id)

        if lead is None or lead.is_deleted:
            raise ValueError("Lead not found.")

        summary = self.summary_repository.get_by_lead_id(lead.id)

        if summary is None:
            return None

        return LeadSummaryResponseDTO.from_entity(summary)
