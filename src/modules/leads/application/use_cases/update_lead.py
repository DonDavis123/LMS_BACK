from src.modules.leads.application.dto.update_lead import (
    UpdateLeadDTO,
    _UNSET,
)
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole


class UpdateLeadUseCase:

    def __init__(
        self,
        lead_repository: LeadRepository,
        user_repository: UserRepository,
    ):
        self.lead_repository = lead_repository
        self.user_repository = user_repository

    def execute(self, data: UpdateLeadDTO):

        existing_lead = self.lead_repository.get_by_id(data.lead_id)

        if existing_lead is None:
            raise ValueError("Lead not found.")

        if data.name is not _UNSET:
            existing_lead.name = data.name

        if data.title is not _UNSET:
            existing_lead.title = data.title

        if data.company_name is not _UNSET:
            existing_lead.company_name = data.company_name

        if data.email is not _UNSET:
            existing_lead.email = data.email

        if data.mobile_number is not _UNSET:
            existing_lead.mobile_number = data.mobile_number

        if data.phone is not _UNSET:
            existing_lead.phone = data.phone

        if data.lead_source is not _UNSET:
            existing_lead.lead_source = data.lead_source

        if data.lead_status is not _UNSET:
            existing_lead.lead_status = data.lead_status

        if data.industry is not _UNSET:
            existing_lead.industry = data.industry

        if data.rating is not _UNSET:
            existing_lead.rating = data.rating

        if data.website is not _UNSET:
            existing_lead.website = data.website

        if data.number_of_employees is not _UNSET:
            existing_lead.number_of_employees = data.number_of_employees

        if data.annual_revenue is not _UNSET:
            existing_lead.annual_revenue = data.annual_revenue

        # Owner
        if data.owner_id is not _UNSET:

            owner = self.user_repository.get_by_id(data.owner_id)

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

            existing_lead.owner_id = data.owner_id

        if data.address is not _UNSET:
            existing_lead.address = data.address

        if data.city is not _UNSET:
            existing_lead.city = data.city

        if data.state is not _UNSET:
            existing_lead.state = data.state

        if data.country is not _UNSET:
            existing_lead.country = data.country

        if data.postal_code is not _UNSET:
            existing_lead.postal_code = data.postal_code

        if data.description is not _UNSET:
            existing_lead.description = data.description

        return self.lead_repository.save(existing_lead)