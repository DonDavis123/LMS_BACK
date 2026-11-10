from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class GetAccountsDTO:
    id: UUID
    account_name: str
    phone: str | None
    website: str | None
    account_owner_id: UUID
    account_owner_name: str | None

    # Read by the export only: the list serializer does not send these, so
    # the list API response is unchanged.
    account_number: str | None = None
    account_type: str | None = None
    industry: str | None = None
    rating: str | None = None
    employees: int | None = None
    annual_revenue: int | None = None
    billing_address: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_country: str | None = None
    billing_postal_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
