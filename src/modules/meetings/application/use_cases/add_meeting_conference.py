from uuid import UUID

from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.application.services.meeting_conference_service import (
    MeetingConferenceService,
)
from src.modules.meetings.domain.entities.meeting import Meeting


class AddMeetingConferenceUseCase:
    """Adds Google Meet to an existing meeting, or retries a failed attempt.

    If the meeting already has a Meet event, its event is re-synced instead
    (also a way to retry a failed update).
    """

    def __init__(
        self,
        meeting_repository: MeetingRepository,
        conference_service: MeetingConferenceService,
    ):
        self.meeting_repository = meeting_repository
        self.conference_service = conference_service

    def execute(self, meeting_id: UUID, current_user_id: UUID | None = None) -> Meeting:
        meeting = self.meeting_repository.get_by_id(meeting_id)
        if meeting is None:
            raise ValueError("Meeting not found.")

        if meeting.external_event_id:
            return self.conference_service.sync(meeting)

        self.conference_service.ensure_can_create(
            meeting.host_id,
            meeting.is_all_day,
            current_user_id,
        )
        return self.conference_service.attach(meeting)
