from src.modules.leads.application.dto.create_lead_dto import CreateLeadDTO
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.domain.entities.lead import Lead


class CreateLeadUseCase:

    def __init__(self, lead_repository: LeadRepository):
        self.lead_repository = lead_repository

    def execute(self, data: CreateLeadDTO) -> Lead:

        lead = Lead.create(
            lead_generator=data.lead_generator,
            client_partner_name=data.client_partner_name,
            mobile_number=data.mobile_number,
            email=data.email,
            city_location=data.city_location,
            business_type=data.business_type,
            remarks=data.remarks,
            lead_source=data.lead_source,
        )

        return self.lead_repository.save(lead)