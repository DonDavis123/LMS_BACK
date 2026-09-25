from uuid import UUID

from src.modules.contacts.application.interfaces.contact_repository import ContactRepository
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.meetings.application.dto.create_meeting import CreateMeetingDTO
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.users.application.interfaces.user_repository import UserRepository


class CreateMeetingUseCase:
    def __init__(
        self,
        meeting_repository: MeetingRepository,
        user_repository: UserRepository,
        lead_repository: LeadRepository,
        contact_repository: ContactRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.meeting_repository = meeting_repository
        self.user_repository = user_repository
        self.lead_repository = lead_repository
        self.contact_repository = contact_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, data: CreateMeetingDTO) -> Meeting:
        self._validate_users(data.host_id, data.created_by_id)
        self._validate_related(data.related_record_type, data.related_record_ids)
        self._validate_participants(data.participant_groups)

        meeting = Meeting.create(
            title=data.title,
            start_at=data.start_at,
            end_at=data.end_at,
            host_id=data.host_id,
            created_by_id=data.created_by_id,
            description=data.description,
            location=data.location,
            is_all_day=data.is_all_day,
        )

        def creation() -> Meeting:
            saved = self.meeting_repository.save_with_relationships(
                meeting,
                data.related_record_type,
                tuple(data.related_record_ids),
                tuple(data.participant_groups),
            )

            targets = [("MEETING", saved.id)]
            targets.extend(self._related_targets(data.related_record_type, data.related_record_ids))

            self.timeline_recorder.record(
                event_type="MEETING_CREATED",
                actor_id=saved.created_by_id,
                message=f"Meeting {saved.title} was created.",
                metadata={
                    "meeting_id": str(saved.id),
                    "title": saved.title,
                },
                targets=targets,
            )
            return saved

        return self.transaction_manager.execute(creation)

    @staticmethod
    def _related_targets(record_type, record_ids) -> list[tuple[str, UUID]]:
        if record_type is None:
            return []
        return [(record_type.value, record_id) for record_id in record_ids]

    def _validate_users(self, host_id: UUID, created_by_id: UUID) -> None:
        host = self.user_repository.get_by_id(host_id)
        if host is None or not host.is_active:
            raise ValueError("Meeting host does not exist or is inactive.")
        creator = self.user_repository.get_by_id(created_by_id)
        if creator is None or not creator.is_active:
            raise ValueError("Meeting creator does not exist or is inactive.")

    def _validate_related(self, record_type, record_ids) -> None:
        if not record_ids:
            if record_type is not None:
                raise ValueError("Related record IDs are required when Related To type is supplied.")
            return
        if record_type is None:
            raise ValueError("Related record type is required when related records are supplied.")
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("Duplicate Related To records are not allowed.")
        if record_type == MeetingRelatedRecordType.LEAD:
            for record_id in record_ids:
                lead = self.lead_repository.get_by_id(record_id)
                if lead is None or lead.is_deleted:
                    raise ValueError("Selected lead not found or is deleted.")
        elif record_type == MeetingRelatedRecordType.CONTACT:
            for record_id in record_ids:
                contact = self.contact_repository.get_by_id(record_id)
                if contact is None or contact.is_deleted:
                    raise ValueError("Selected contact not found or is deleted.")
        else:
            raise ValueError("Unsupported Related To type.")

    def _validate_participants(self, groups) -> None:
        seen: set[UUID] = set()
        for group in groups:
            if len(group.participant_ids) != len(set(group.participant_ids)):
                raise ValueError("Duplicate participants are not allowed.")
            for participant_id in group.participant_ids:
                if participant_id in seen:
                    raise ValueError("The same participant cannot be added more than once.")
                seen.add(participant_id)
                if group.participant_type == MeetingParticipantType.LEAD:
                    item = self.lead_repository.get_by_id(participant_id)
                    if item is None or item.is_deleted:
                        raise ValueError("Selected lead participant not found or is deleted.")
                elif group.participant_type == MeetingParticipantType.CONTACT:
                    item = self.contact_repository.get_by_id(participant_id)
                    if item is None or item.is_deleted:
                        raise ValueError("Selected contact participant not found or is deleted.")
                elif group.participant_type == MeetingParticipantType.USER:
                    item = self.user_repository.get_by_id(participant_id)
                    if item is None or not item.is_active:
                        raise ValueError("Selected user participant does not exist or is inactive.")
                else:
                    raise ValueError("Unsupported participant type.")
