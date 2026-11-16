from dataclasses import dataclass
from uuid import UUID

from src.modules.meetings.application.dto.participant_group import ParticipantGroup
from src.modules.meetings.application.dto.related_group import RelatedGroup


_UNSET = object()


@dataclass(frozen=True)
class UpdateMeetingDTO:
    meeting_id: UUID
    fields: dict[str, object]
    related_groups: tuple[RelatedGroup, ...] | object = _UNSET
    participant_groups: tuple[ParticipantGroup, ...] | object = _UNSET
