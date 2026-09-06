from src.modules.leads.application.dto.create_lead_dto import CreateLeadDTO
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.domain.entities.lead import Lead


class CreateLeadUseCase:

    def __init__(self, lead_repository: LeadRepository):
        self.lead_repository = lead_repository

    def execute(self, data: CreateLeadDTO) -> Lead:

        lead = Lead.create(
            name=data.name,
            company_name=data.company_name,
            email=data.email,
            mobile_number=data.mobile_number,
            lead_source=data.lead_source,
            owner_id=data.owner_id,
        )

        return self.lead_repository.save(lead)