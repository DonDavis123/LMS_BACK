from dataclasses import dataclass

from src.modules.leads.domain.entities.business_type import BusinessType


@dataclass
class CreateLeadDTO:
    lead_generator: str
    client_partner_name: str
    mobile_number: str
    email: str | None
    city_location: str | None
    business_type: BusinessType
    remarks: str | None
    lead_source: str