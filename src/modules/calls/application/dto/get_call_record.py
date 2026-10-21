from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.calls.application.dto.get_call import GetCallDTO


@dataclass(frozen=True)
class GetCallRecordDTO:
    """One row of the calls table: a lead or a contact and its calls.

    A lead/contact is listed ONCE, however many calls were logged on it.
    ``latest_call`` is its most recent call (by start time), ``call_count``
    counts every active call on the record and ``last_updated_at`` is the
    last time any of those calls was logged or edited. ``latest_update`` is
    the newest call timeline event on the record (call logged / edited /
    deleted), filled in by the use case from the timeline.
    """

    record_type: str  # "LEAD" | "CONTACT"
    record_id: UUID
    record_name: str | None
    call_count: int
    last_updated_at: datetime
    latest_call: GetCallDTO
    latest_update: dict | None = None
