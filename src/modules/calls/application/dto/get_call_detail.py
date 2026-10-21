from dataclasses import dataclass
from uuid import UUID

from src.modules.calls.application.dto.get_call import GetCallDTO


@dataclass(frozen=True)
class GetCallDetailDTO:
    """Full call detail: the call, its edit history and sibling calls.

    ``related_calls`` holds the OTHER calls logged on the same lead/contact
    (newest first, capped), while ``total_calls_for_record`` counts every
    active call on that record, including this one.
    """

    call: GetCallDTO
    related_record_type: str  # "LEAD" | "CONTACT"
    related_record_id: UUID
    related_record_name: str | None
    change_history: list[dict]
    related_calls: list[GetCallDTO]
    total_calls_for_record: int
