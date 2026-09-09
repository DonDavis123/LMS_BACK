from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class GetAccountDetailsDTO:
    id: UUID

    account_owner_id: UUID
    account_owner_name: str | None

    account_name: str
    account_site: str | None
    account_number: str | None
    account_type: str | None
    industry: str | None
    annual_revenue: int | None
    rating: str | None
    phone: str | None
    website: str | None
    ticker_symbol: str | None
    ownership: str
    employees: int | None
    sic_code: str | None

    billing_address: str | None
    billing_city: str | None
    billing_state: str | None
    billing_country: str | None
    billing_postal_code: str | None

    description: str | None

    created_by_id: UUID
    created_at: datetime

    modified_by_id: UUID
    updated_at: datetime