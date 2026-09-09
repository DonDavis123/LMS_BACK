from uuid import UUID

from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.domain.entities.lead import Lead


class GetLeadDetailsUseCase:

    def __init__(self, lead_repository: LeadRepository):
        self.lead_repository = lead_repository

    def execute(self, lead_id: UUID) -> tuple[Lead, str]:

        result = self.lead_repository.get_by_id_with_owner(lead_id)

        if result is None:
            raise ValueError("Lead not found.")

        return result