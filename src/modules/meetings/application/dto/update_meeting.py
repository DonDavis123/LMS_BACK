from dataclasses import dataclass
from uuid import UUID

from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.meetings.application.dto.participant_group import ParticipantGroup


_UNSET = object()


@dataclass(frozen=True)
class UpdateMeetingDTO:
    meeting_id: UUID
    fields: dict[str, object]
    related_record_type: MeetingRelatedRecordType | None | object = _UNSET
    related_record_ids: tuple[UUID, ...] | object = _UNSET
    participant_groups: tuple[ParticipantGroup, ...] | object = _UNSET
