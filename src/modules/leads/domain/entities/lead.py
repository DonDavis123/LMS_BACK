from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from .lead_industry import LeadIndustry
from .lead_rating import LeadRating
from .lead_source import LeadSource
from .lead_status import LeadStatus


@dataclass
class Lead:
    id: UUID
    name: str
    title: str | None
    company_name: str
    email: str | None
    mobile_number: str | None
    phone: str | None
    lead_source: LeadSource
    lead_status: LeadStatus
    industry: LeadIndustry
    rating: LeadRating
    website: str | None
    number_of_employees: int | None
    annual_revenue: int | None
    owner_id: UUID
    address: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    description: str | None
    is_deleted: bool
    is_converted: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        name: str,
        title: str | None,
        company_name: str,
        email: str | None,
        mobile_number: str | None,
        phone: str | None,
        lead_source: LeadSource,
        lead_status: LeadStatus,
        industry: LeadIndustry,
        rating: LeadRating,
        website: str | None,
        number_of_employees: int | None,
        annual_revenue: int | None,
        owner_id: UUID,
        address: str | None,
        city: str | None,
        state: str | None,
        country: str | None,
        postal_code: str | None,
        description: str | None,
    ) -> "Lead":
        now = datetime.utcnow()

        return cls(
            id=uuid4(),
            name=name,
            title=title,
            company_name=company_name,
            email=email,
            mobile_number=mobile_number,
            phone=phone,
            lead_source=lead_source,
            lead_status=lead_status,
            industry=industry,
            rating=rating,
            website=website,
            number_of_employees=number_of_employees,
            annual_revenue=annual_revenue,
            owner_id=owner_id,
            address=address,
            city=city,
            state=state,
            country=country,
            postal_code=postal_code,
            description=description,

            # Backend-controlled state
            is_deleted=False,
            is_converted=False,

            # Backend-controlled timestamps
            created_at=now,
            updated_at=now,
        )

    def soft_delete(self) -> None:
        if self.is_deleted:
            raise ValueError("Lead is already deleted.")

        if self.is_converted:
            raise ValueError("Converted lead cannot be deleted.")

        self.is_deleted = True

    def convert(self) -> None:
        if self.is_deleted:
            raise ValueError("Deleted lead cannot be converted.")

        if self.is_converted:
            raise ValueError("Lead is already converted.")

        self.is_converted = True