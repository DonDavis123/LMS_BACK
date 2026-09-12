from dataclasses import dataclass
from uuid import UUID


@dataclass
class DeleteContactDTO:
    contact_id: UUID