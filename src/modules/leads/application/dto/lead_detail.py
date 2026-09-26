from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .owner_response import OwnerResponseDTO


@dataclass
class LeadDetailResponseDTO:

    id: UUID

    name: str
    title: str | None

    company_name: str | None
    email: str | None
    mobile_number: str
    phone: str | None

    lead_source: str
    lead_status: str
    industry: str
    rating: str

    website: str | None
    number_of_employees: int | None
    annual_revenue: int | None

    owner: OwnerResponseDTO

    address: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None

    description: str | None

    created_at: datetime
    updated_at: datetime