from datetime import datetime, timezone
from uuid import UUID

from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)
from src.modules.leads.domain.entities.business_type import BusinessType
from src.modules.leads.domain.entities.lead import Lead


class UpdateLeadUseCase:

    def __init__(
        self,
        lead_repository: LeadRepository,
    ):
        self.lead_repository = lead_repository

    def execute(
        self,
        lead_id: UUID,
        client_partner_name: str | None = None,
        mobile_number: str | None = None,
        email: str | None = None,
        city_location: str | None = None,
        business_type: BusinessType | None = None,
        lead_source: str | None = None,
        remarks: str | None = None,
    ) -> Lead:

        existing_lead = self.lead_repository.get_by_id(
            lead_id
        )

        if existing_lead is None:
            raise ValueError(
                "Lead not found."
            )

        if client_partner_name is not None:
            existing_lead.client_partner_name = (
                client_partner_name
            )

        if mobile_number is not None:
            existing_lead.mobile_number = (
                mobile_number
            )

        if email is not None:
            existing_lead.email = email

        if city_location is not None:
            existing_lead.city_location = city_location

        if business_type is not None:
            existing_lead.business_type = business_type

        if lead_source is not None:
            existing_lead.lead_source = lead_source

        if remarks is not None:
            existing_lead.remarks = remarks

        existing_lead.updated_at = datetime.now(
            timezone.utc
        )

        return self.lead_repository.save(
            existing_lead
        )