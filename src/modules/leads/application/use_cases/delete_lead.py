from uuid import UUID

from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)


class DeleteLeadUseCase:

    def __init__(
        self,
        lead_repository: LeadRepository,
    ):
        self.lead_repository = lead_repository

    def execute(self, lead_id: UUID) -> None:

        lead = self.lead_repository.get_by_id(lead_id)

        if lead is None:
            raise ValueError("Lead not found.")

        lead.soft_delete()

        self.lead_repository.save(lead)