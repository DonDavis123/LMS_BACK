from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetCallRecordHistoryDTO:
    """Detailed history of every call logged on one lead / contact.

    ``events`` is newest first. Each event carries a ``call`` snapshot (start
    time, duration, outcome, type, notes) as the call was at that moment.
    """

    related_record_type: str  # "LEAD" | "CONTACT"
    related_record_id: UUID
    related_record_name: str | None
    total_calls_for_record: int
    events: list[dict]
