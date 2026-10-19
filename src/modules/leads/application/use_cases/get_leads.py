from src.modules.leads.application.dto.get_leads import LeadResponseDTO
from src.modules.leads.application.dto.owner_response import OwnerResponseDTO
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.domain.entities.option_text import option_text
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class GetLeadsUseCase:

    def __init__(self, lead_repository: LeadRepository):
        self.lead_repository = lead_repository

    def execute(self, query: ListQuery) -> PaginatedResult[LeadResponseDTO]:
        result = self.lead_repository.get_all_with_owner(query)

        return PaginatedResult(
            results=[
                LeadResponseDTO(
                    id=lead.id,
                    name=lead.name,
                    company_name=lead.company_name,
                    email=lead.email,
                    phone=lead.phone,
                    mobile_number=lead.mobile_number,
                    lead_source=option_text(lead.lead_source),
                    lead_status=option_text(lead.lead_status),
                    owner=OwnerResponseDTO(
                        id=lead.owner_id,
                        name=owner_name,
                    ),
                    created_at=lead.created_at,
                    updated_at=lead.updated_at,
                )
                for lead, owner_name in result.results
            ],
            page=result.page,
            page_size=result.page_size,
            total=result.total,
        )
