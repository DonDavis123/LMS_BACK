from dataclasses import dataclass
from uuid import UUID

from src.modules.leads.domain.entities.lead_source import LeadSource


@dataclass
class CreateLeadDTO:
    name: str
    company_name: str
    email: str | None
    mobile_number: str
    lead_source: LeadSource
    owner_id: UUID