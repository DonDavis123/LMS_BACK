from uuid import UUID

from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.reminders.application.services.reminder_sync_service import ReminderSyncService
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder


class DeleteMeetingUseCase:
    def __init__(
        self,
        meeting_repository: MeetingRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
        reminder_sync_service: ReminderSyncService | None = None,
    ):
        self.meeting_repository = meeting_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager
        self.reminder_sync_service = reminder_sync_service

    def execute(self, meeting_id: UUID, current_user_id=None) -> None:
        meeting = self.meeting_repository.get_by_id(meeting_id)
        if meeting is None:
            raise ValueError("Meeting not found.")
        if meeting.is_deleted:
            raise ValueError("Meeting is already deleted.")

        def deletion():
            detail = self.meeting_repository.get_by_id_with_details(meeting_id)
            if detail is None:
                raise ValueError("Meeting not found.")

            targets = [("MEETING", meeting.id)]
            seen = set(targets)
            for related in detail.related_to:
                target = (related.record_type.value, related.id)
                if target not in seen:
                    targets.append(target)
                    seen.add(target)

            deleted = self.meeting_repository.soft_delete_by_id(meeting_id)
            if deleted is None:
                raise ValueError("Meeting not found.")

            if self.reminder_sync_service is not None:
                self.reminder_sync_service.delete_for_meeting(meeting_id)

            self.timeline_recorder.record(
                event_type="MEETING_DELETED",
                actor_id=current_user_id or meeting.created_by_id,
                message=f"Meeting {meeting.title} was deleted.",
                metadata={
                    "meeting_id": str(meeting.id),
                    "title": meeting.title,
                },
                targets=targets,
            )

        self.transaction_manager.execute(deletion)
