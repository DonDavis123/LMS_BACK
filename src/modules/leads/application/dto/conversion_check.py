from dataclasses import dataclass
from uuid import UUID


@dataclass
class ConversionCheckDTO:
    lead_id: UUID
    account_matches: list
    contact_matches: list