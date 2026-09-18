from src.modules.leads.application.dto.get_leads import LeadResponseDTO
from src.modules.leads.application.dto.owner_response import OwnerResponseDTO
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
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
                    mobile_number=lead.mobile_number,
                    lead_source=lead.lead_source.value,
                    lead_status=lead.lead_status.value,
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
