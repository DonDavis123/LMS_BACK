from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.meetings.application.dto.participant_group import ParticipantGroup
from src.modules.meetings.application.dto.related_group import RelatedGroup


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
    reminder_at: datetime | None = None
    related_groups: tuple[RelatedGroup, ...] = ()
    participant_groups: tuple[ParticipantGroup, ...] = ()
    add_google_meet: bool = False
    # None follows ``add_google_meet`` (a Meet meeting has always been emailed).
    send_email_notifications: bool | None = None
