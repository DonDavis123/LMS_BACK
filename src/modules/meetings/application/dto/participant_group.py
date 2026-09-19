from dataclasses import dataclass
from uuid import UUID

from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType


@dataclass(frozen=True)
class ParticipantGroup:
    participant_type: MeetingParticipantType
    participant_ids: tuple[UUID, ...]
