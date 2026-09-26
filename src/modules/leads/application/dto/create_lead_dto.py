from dataclasses import dataclass
from uuid import UUID

from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus


@dataclass
class CreateLeadDTO:
    name: str
    title: str | None
    company_name: str | None
    email: str | None
    mobile_number: str | None
    phone: str | None
    lead_source: LeadSource | None
    lead_status: LeadStatus | None
    industry: LeadIndustry | None
    rating: LeadRating | None
    website: str | None
    number_of_employees: int | None
    annual_revenue: int | None
    owner_id: UUID | None
    address: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    description: str | None