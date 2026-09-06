from src.modules.leads.application.dto.lead_response import LeadResponseDTO
from src.modules.leads.application.dto.owner_response import OwnerResponseDTO
from src.modules.leads.application.interfaces.lead_repository import LeadRepository


class GetLeadsUseCase:

    def __init__(self, lead_repository: LeadRepository):
        self.lead_repository = lead_repository

    def execute(self) -> list[LeadResponseDTO]:
        leads = self.lead_repository.get_all_with_owner()

        return [
            LeadResponseDTO(
                id=lead.id,
                name=lead.name,
                company_name=lead.company_name,
                email=lead.email,
                mobile_number=lead.mobile_number,
                lead_source=lead.lead_source.value,
                owner=OwnerResponseDTO(
                    id=lead.owner_id,
                    name=owner_name,
                ),
                created_at=lead.created_at,
                updated_at=lead.updated_at,
            )
            for lead, owner_name in leads
        ]