from datetime import datetime
from uuid import UUID

from src.modules.contacts.application.interfaces.contact_repository import ContactRepository
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.meetings.application.dto.update_meeting import UpdateMeetingDTO, _UNSET
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.meetings.application.dto.participant_group import ParticipantGroup
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.users.application.interfaces.user_repository import UserRepository


class UpdateMeetingUseCase:
    def __init__(
        self,
        meeting_repository: MeetingRepository,
        user_repository: UserRepository,
        lead_repository: LeadRepository,
        contact_repository: ContactRepository,
        transaction_manager: TransactionManager,
    ):
        self.meeting_repository = meeting_repository
        self.user_repository = user_repository
        self.lead_repository = lead_repository
        self.contact_repository = contact_repository
        self.transaction_manager = transaction_manager

    def execute(self, data: UpdateMeetingDTO):
        meeting = self.meeting_repository.get_by_id(data.meeting_id)
        if meeting is None:
            raise ValueError("Meeting not found.")
        if meeting.is_deleted:
            raise ValueError("Deleted Meeting cannot be updated.")

        fields = data.fields
        allowed = {"title", "description", "location", "is_all_day", "start_at", "end_at", "host_id"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unsupported Meeting fields: {', '.join(sorted(unknown))}.")

        if "host_id" in fields:
            self._validate_user(fields["host_id"], "Meeting host")

        related_changed = data.related_record_type is not _UNSET or data.related_record_ids is not _UNSET
        if related_changed:
            if data.related_record_type is _UNSET or data.related_record_ids is _UNSET:
                raise ValueError("Related To type and IDs must be supplied together when updating Related To.")
            related_type = data.related_record_type
            related_ids = tuple(data.related_record_ids)
            self._validate_related(related_type, related_ids)
        else:
            related_type = None
            related_ids = ()

        participants_changed = data.participant_groups is not _UNSET
        participant_groups = () if data.participant_groups is _UNSET else tuple(data.participant_groups)
        if participants_changed:
            self._validate_participants(participant_groups)

        existing_detail = None
        if related_changed != participants_changed:
            existing_detail = self.meeting_repository.get_by_id_with_details(meeting.id)

        def update():
            for field, value in fields.items():
                setattr(meeting, field, value)
            if not meeting.title or not meeting.title.strip():
                raise ValueError("Meeting title cannot be empty.")
            if meeting.end_at < meeting.start_at:
                raise ValueError("Meeting end time cannot be earlier than start time.")
            if "host_id" in fields:
                meeting.host_id = fields["host_id"]
            saved = self.meeting_repository.save(meeting)
            if related_changed or participants_changed:
                current_related_type = related_type
                current_related_ids = related_ids
                if not related_changed and existing_detail and existing_detail.related_to:
                    current_related_type = existing_detail.related_to[0].record_type
                    current_related_ids = tuple(item.id for item in existing_detail.related_to)

                current_participants = participant_groups
                if not participants_changed and existing_detail:
                    grouped = {}
                    for participant in existing_detail.participants:
                        grouped.setdefault(participant.participant_type, []).append(participant.id)
                    current_participants = tuple(
                        ParticipantGroup(
                            participant_type=ptype,
                            participant_ids=tuple(ids),
                        )
                        for ptype, ids in grouped.items()
                    )

                self.meeting_repository.replace_relationships(
                    meeting.id,
                    current_related_type,
                    current_related_ids,
                    current_participants,
                )
            return self.meeting_repository.get_by_id(meeting.id)

        return self.transaction_manager.execute(update)

    def _validate_user(self, user_id: UUID, label: str) -> None:
        user = self.user_repository.get_by_id(user_id)
        if user is None or not user.is_active:
            raise ValueError(f"{label} does not exist or is inactive.")

    def _validate_related(self, record_type, record_ids):
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

    def _validate_participants(self, groups):
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
                    self._validate_user(participant_id, "Selected user participant")
                else:
                    raise ValueError("Unsupported participant type.")
