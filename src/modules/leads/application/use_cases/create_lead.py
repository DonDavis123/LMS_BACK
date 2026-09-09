from uuid import UUID

from src.modules.leads.application.dto.create_lead_dto import CreateLeadDTO
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.leads.domain.entities.lead import Lead
from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole


class CreateLeadUseCase:
    def __init__(
        self,
        lead_repository: LeadRepository,
        user_repository: UserRepository,
    ):
        self.lead_repository = lead_repository
        self.user_repository = user_repository

    def execute(
        self,
        data: CreateLeadDTO,
        current_user_id: UUID,
    ) -> Lead:
        # Use selected owner if provided.
        # Otherwise, use the currently authenticated user.
        owner_id = data.owner_id or current_user_id

        owner = self.user_repository.get_by_id(owner_id)

        if owner is None:
            raise ValueError("Selected owner does not exist.")

        if not owner.is_active:
            raise ValueError("Selected owner is inactive.")

        if owner.role not in {
            UserRole.ADMIN,
            UserRole.SUPERADMIN,
        }:
            raise ValueError(
                "Selected owner must be an ADMIN or SUPERADMIN."
            )

        lead = Lead.create(
            name=data.name,
            title=data.title,
            company_name=data.company_name,
            email=data.email,
            mobile_number=data.mobile_number,
            phone=data.phone,
            lead_source=data.lead_source or LeadSource.NONE,
            lead_status=data.lead_status or LeadStatus.NONE,
            industry=data.industry or LeadIndustry.NONE,
            rating=data.rating or LeadRating.NONE,
            website=data.website,
            number_of_employees=data.number_of_employees,
            annual_revenue=data.annual_revenue,
            owner_id=owner_id,
            address=data.address,
            city=data.city,
            state=data.state,
            country=data.country,
            postal_code=data.postal_code,
            description=data.description,
        )

        return self.lead_repository.save(lead)