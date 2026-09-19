from dataclasses import dataclass
from uuid import UUID

from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.meetings.domain.entities.meeting import Meeting


@dataclass(frozen=True)
class MeetingRelatedRecordDTO:
    id: UUID
    record_type: MeetingRelatedRecordType
    name: str


@dataclass(frozen=True)
class MeetingParticipantDTO:
    id: UUID
    participant_type: MeetingParticipantType
    name: str


@dataclass(frozen=True)
class GetMeetingDTO:
    meeting: Meeting
    host_id: UUID
    host_name: str
    created_by_id: UUID
    created_by_name: str
    related_to: tuple[MeetingRelatedRecordDTO, ...]
    participants: tuple[MeetingParticipantDTO, ...]
