from dataclasses import dataclass
from uuid import UUID

from src.modules.leads.domain.entities.lead_industry import LeadIndustry
from src.modules.leads.domain.entities.lead_rating import LeadRating
from src.modules.leads.domain.entities.lead_source import LeadSource
from src.modules.leads.domain.entities.lead_status import LeadStatus


_UNSET = object()


@dataclass
class UpdateLeadDTO:
    lead_id: UUID

    name: str | None | object = _UNSET
    title: str | None | object = _UNSET

    company_name: str | None | object = _UNSET
    email: str | None | object = _UNSET
    mobile_number: str | None | object = _UNSET
    phone: str | None | object = _UNSET

    lead_source: LeadSource | object = _UNSET
    lead_status: LeadStatus | object = _UNSET
    industry: LeadIndustry | object = _UNSET
    rating: LeadRating | object = _UNSET

    website: str | None | object = _UNSET
    number_of_employees: int | None | object = _UNSET
    annual_revenue: int | None | object = _UNSET

    # Ownership
    owner_id: UUID | object = _UNSET

    address: str | None | object = _UNSET
    city: str | None | object = _UNSET
    state: str | None | object = _UNSET
    country: str | None | object = _UNSET
    postal_code: str | None | object = _UNSET

    description: str | None | object = _UNSET