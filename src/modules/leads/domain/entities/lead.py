from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from .lead_source import LeadSource


@dataclass
class Lead:
    id: UUID
    name: str
    company_name: str
    email: str | None
    mobile_number: str
    lead_source: LeadSource
    owner_id: UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        name: str,
        company_name: str,
        email: str | None,
        mobile_number: str,
        lead_source: LeadSource,
        owner_id: UUID,
    ) -> "Lead":

        now = datetime.utcnow()

        return cls(
            id=uuid4(),
            name=name,
            company_name=company_name,
            email=email,
            mobile_number=mobile_number,
            lead_source=lead_source,
            owner_id=owner_id,
            created_at=now,
            updated_at=now,
        )