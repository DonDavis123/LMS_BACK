from dataclasses import dataclass, field
from uuid import UUID

from src.modules.accounts.application.dto.account_document import (
    NewAccountDocumentDTO,
)


@dataclass
class CreateAccountDTO:
    account_owner_id: UUID | None

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

    # Billing information
    billing_address: str | None
    billing_city: str | None
    billing_state: str | None
    billing_country: str | None
    billing_postal_code: str | None

    # Description
    description: str | None

    # Documents (name + URL) attached when the account is created
    documents: list[NewAccountDocumentDTO] = field(default_factory=list)
