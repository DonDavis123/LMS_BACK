from dataclasses import dataclass
from uuid import UUID


@dataclass
class UpdateContactDTO:
    contact_id: UUID
    fields: dict