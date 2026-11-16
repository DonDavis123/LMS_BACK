from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType


@dataclass(frozen=True)
class GetMeetingsDTO:
    id: UUID
    title: str
    start_at: datetime
    end_at: datetime
    reminder_at: datetime | None
    related_to_type: MeetingRelatedRecordType | None
    related_to_names: tuple[str, ...]
    contact_names: tuple[str, ...]
    host_id: UUID
    host_name: str
    meet_link: str | None = None
    conference_status: str = "none"
    # (type, name) for every related record, so a list can show leads and
    # contacts side by side. `related_to_type` stays the first record's type.
    related_to_items: tuple[tuple[MeetingRelatedRecordType, str], ...] = ()
