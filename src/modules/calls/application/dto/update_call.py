from dataclasses import dataclass
from uuid import UUID


@dataclass
class UpdateCallDTO:
    call_id: UUID
    fields: dict[str, object]
