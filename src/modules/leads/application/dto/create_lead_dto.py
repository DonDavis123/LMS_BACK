from dataclasses import dataclass
from uuid import UUID



@dataclass
class CreateLeadDTO:
    name: str
    title: str | None
    company_name: str | None
    email: str | None
    mobile_number: str | None
    phone: str | None
    lead_source: str | None
    lead_status: str | None
    industry: str | None
    rating: str | None
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