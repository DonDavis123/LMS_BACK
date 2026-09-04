from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from .business_type import BusinessType


@dataclass
class Lead:
    id: UUID
    lead_generator: str
    client_partner_name: str
    mobile_number: str
    email: str | None
    city_location: str | None
    business_type: BusinessType
    remarks: str | None
    lead_source: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        lead_generator: str,
        client_partner_name: str,
        mobile_number: str,
        email: str | None,
        city_location: str | None,
        business_type: BusinessType,
        remarks: str | None,
        lead_source: str,
    ) -> "Lead":

        now = datetime.utcnow()

        return cls(
            id=uuid4(),
            lead_generator=lead_generator,
            client_partner_name=client_partner_name,
            mobile_number=mobile_number,
            email=email,
            city_location=city_location,
            business_type=business_type,
            remarks=remarks,
            lead_source=lead_source,
            created_at=now,
            updated_at=now,
        )