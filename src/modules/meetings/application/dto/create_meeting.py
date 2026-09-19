from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType

from src.modules.meetings.application.dto.participant_group import ParticipantGroup


@dataclass(frozen=True)
class CreateMeetingDTO:
    title: str
    start_at: datetime
    end_at: datetime
    host_id: UUID
    created_by_id: UUID
    description: str | None = None
    location: str | None = None
    is_all_day: bool = False
    related_record_type: MeetingRelatedRecordType | None = None
    related_record_ids: tuple[UUID, ...] = ()
    participant_groups: tuple[ParticipantGroup, ...] = ()
