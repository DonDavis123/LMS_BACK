from dataclasses import dataclass
from uuid import UUID
from datetime import date


@dataclass
class ConvertAccountDTO:
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


@dataclass
class ConvertContactDTO:
    name: str
    email: str | None
    secondary_email: str | None
    phone: str | None
    other_phone: str | None
    mobile: str | None
    home_phone: str | None
    assistant_phone: str | None

    title: str | None
    department: str | None
    lead_source: str | None
    vendor_name: str | None

    date_of_birth: date | None
    assistant: str | None
    email_opt_out: bool
    reporting_to_id: UUID | None

    mailing_address: str | None
    mailing_city: str | None
    mailing_state: str | None
    mailing_country: str | None
    mailing_postal_code: str | None
    other_address: str | None

    description: str | None


@dataclass
class ConvertLeadDTO:
    lead_id: UUID

    account_action: str
    account_id: UUID | None
    account: ConvertAccountDTO | None

    contact_action: str
    contact_id: UUID | None
    contact: ConvertContactDTO | None