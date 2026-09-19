from uuid import UUID

from src.modules.meetings.application.dto.get_meeting import GetMeetingDTO
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository


class GetMeetingUseCase:
    def __init__(self, meeting_repository: MeetingRepository):
        self.meeting_repository = meeting_repository

    def execute(self, meeting_id: UUID) -> GetMeetingDTO | None:
        return self.meeting_repository.get_by_id_with_details(meeting_id)
