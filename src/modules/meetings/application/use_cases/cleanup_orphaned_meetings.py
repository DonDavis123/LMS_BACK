from uuid import UUID

from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType


class CleanupOrphanedMeetingsUseCase:
    """Soft-delete active Meetings that no longer have an active Related To record."""

    def __init__(self, meeting_repository: MeetingRepository):
        self.meeting_repository = meeting_repository

    def execute(self, record_type: MeetingRelatedRecordType, record_id: UUID) -> list[UUID]:
        if record_type not in {MeetingRelatedRecordType.LEAD, MeetingRelatedRecordType.CONTACT}:
            raise ValueError("Only Lead or Contact records can trigger Meeting orphan cleanup.")
        return self.meeting_repository.soft_delete_if_orphaned(record_type, record_id)
