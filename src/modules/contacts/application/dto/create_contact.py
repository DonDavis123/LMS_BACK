from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass
class CreateContactDTO:
    account_id: UUID | None
    contact_owner_id: UUID | None

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