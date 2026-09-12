from dataclasses import dataclass
from uuid import UUID


@dataclass
class UpdateAccountDTO:
    account_id: UUID

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
    ownership: str | None
    employees: int | None
    sic_code: str | None

    billing_address: str | None
    billing_city: str | None
    billing_state: str | None
    billing_country: str | None
    billing_postal_code: str | None

    description: str | None