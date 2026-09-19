from uuid import UUID

from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class DeleteMeetingUseCase:
    def __init__(
        self,
        meeting_repository: MeetingRepository,
        transaction_manager: TransactionManager,
    ):
        self.meeting_repository = meeting_repository
        self.transaction_manager = transaction_manager

    def execute(self, meeting_id: UUID) -> None:
        meeting = self.meeting_repository.get_by_id(meeting_id)
        if meeting is None:
            raise ValueError("Meeting not found.")
        if meeting.is_deleted:
            raise ValueError("Meeting is already deleted.")

        def deletion():
            deleted = self.meeting_repository.soft_delete_by_id(meeting_id)
            if deleted is None:
                raise ValueError("Meeting not found.")

        self.transaction_manager.execute(deletion)
