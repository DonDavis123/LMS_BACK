from src.modules.meetings.application.dto.get_meetings import GetMeetingsDTO
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class GetMeetingsUseCase:
    def __init__(self, meeting_repository: MeetingRepository):
        self.meeting_repository = meeting_repository

    def execute(self, query: ListQuery) -> PaginatedResult[GetMeetingsDTO]:
        return self.meeting_repository.get_all(query)
