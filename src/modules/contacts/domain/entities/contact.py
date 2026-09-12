from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4


@dataclass
class Contact:
    id: UUID

    # Relationship
    account_id: UUID | None
    contact_owner_id: UUID

    # Contact information
    name: str
    email: str | None
    secondary_email: str | None
    phone: str | None
    other_phone: str | None
    mobile: str | None
    home_phone: str | None
    assistant_phone: str | None

    # Professional information
    title: str | None
    department: str | None
    lead_source: str | None
    vendor_name: str | None

    # Personal information
    date_of_birth: date | None
    assistant: str | None
    email_opt_out: bool
    reporting_to_id: UUID | None

    # Address
    mailing_address: str | None
    mailing_city: str | None
    mailing_state: str | None
    mailing_country: str | None
    mailing_postal_code: str | None
    other_address: str | None

    # Description
    description: str | None

    # Audit fields
    created_by_id: UUID
    created_at: datetime
    modified_by_id: UUID
    updated_at: datetime
    is_deleted: bool

    @classmethod
    def create(
        cls,
        account_id: UUID | None,
        contact_owner_id: UUID,
        name: str,
        email: str | None,
        secondary_email: str | None,
        phone: str | None,
        other_phone: str | None,
        mobile: str | None,
        home_phone: str | None,
        assistant_phone: str | None,
        title: str | None,
        department: str | None,
        lead_source: str | None,
        vendor_name: str | None,
        date_of_birth: date | None,
        assistant: str | None,
        email_opt_out: bool,
        reporting_to_id: UUID | None,
        mailing_address: str | None,
        mailing_city: str | None,
        mailing_state: str | None,
        mailing_country: str | None,
        mailing_postal_code: str | None,
        other_address: str | None,
        description: str | None,
        created_by_id: UUID,
    ) -> "Contact":
        now = datetime.utcnow()

        return cls(
            id=uuid4(),
            account_id=account_id,
            contact_owner_id=contact_owner_id,
            name=name,
            email=email,
            secondary_email=secondary_email,
            phone=phone,
            other_phone=other_phone,
            mobile=mobile,
            home_phone=home_phone,
            assistant_phone=assistant_phone,
            title=title,
            department=department,
            lead_source=lead_source,
            vendor_name=vendor_name,
            date_of_birth=date_of_birth,
            assistant=assistant,
            email_opt_out=email_opt_out,
            reporting_to_id=reporting_to_id,
            mailing_address=mailing_address,
            mailing_city=mailing_city,
            mailing_state=mailing_state,
            mailing_country=mailing_country,
            mailing_postal_code=mailing_postal_code,
            other_address=other_address,
            description=description,
            created_by_id=created_by_id,
            created_at=now,
            modified_by_id=created_by_id,
            updated_at=now,
            is_deleted=False,
        )