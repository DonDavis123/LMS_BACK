from uuid import UUID

from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)
from src.modules.leads.domain.entities.lead import Lead
from src.modules.leads.domain.entities.lead_source import LeadSource


_UNSET = object()


class UpdateLeadUseCase:

    def __init__(
        self,
        lead_repository: LeadRepository,
    ):
        self.lead_repository = lead_repository

    def execute(
        self,
        lead_id: UUID,
        name: str | None = None,
        company_name: str | None = None,
        email: str | None | object = _UNSET,
        mobile_number: str | None = None,
        lead_source: LeadSource | None = None,
    ) -> Lead:

        existing_lead = self.lead_repository.get_by_id(
            lead_id
        )

        if existing_lead is None:
            raise ValueError(
                "Lead not found."
            )

        if name is not None:
            existing_lead.name = name

        if company_name is not None:
            existing_lead.company_name = company_name

        if email is not _UNSET:
            existing_lead.email = email

        if mobile_number is not None:
            existing_lead.mobile_number = mobile_number

        if lead_source is not None:
            existing_lead.lead_source = lead_source

        return self.lead_repository.save(
            existing_lead
        )