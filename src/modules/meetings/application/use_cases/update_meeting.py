from uuid import UUID

from src.modules.contacts.application.interfaces.contact_repository import ContactRepository
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.meetings.application.dto.participant_group import ParticipantGroup
from src.modules.meetings.application.dto.update_meeting import UpdateMeetingDTO, _UNSET
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.timeline.application.services.change_tracker import (
    build_field_changes,
    format_field_changes,
    resolve_relationship_changes,
)
from src.modules.users.application.interfaces.user_repository import UserRepository


class UpdateMeetingUseCase:
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

    def execute(self, data: UpdateMeetingDTO, current_user_id: UUID | None = None):
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

        existing_detail = self.meeting_repository.get_by_id_with_details(meeting.id)
        if existing_detail is None:
            raise ValueError("Meeting not found.")

        updateable_fields = (
            "title",
            "description",
            "location",
            "is_all_day",
            "start_at",
            "end_at",
            "host_id",
        )
        old_values = {field: getattr(meeting, field) for field in updateable_fields}

        def update():
            for field, value in fields.items():
                setattr(meeting, field, value)

            if not meeting.title or not meeting.title.strip():
                raise ValueError("Meeting title cannot be empty.")
            if meeting.end_at < meeting.start_at:
                raise ValueError("Meeting end time cannot be earlier than start time.")

            saved = self.meeting_repository.save(meeting)

            if related_changed or participants_changed:
                current_related_type = related_type
                current_related_ids = related_ids
                if not related_changed and existing_detail.related_to:
                    current_related_type = existing_detail.related_to[0].record_type
                    current_related_ids = tuple(item.id for item in existing_detail.related_to)

                current_participants = participant_groups
                if not participants_changed:
                    grouped: dict[MeetingParticipantType, list[UUID]] = {}
                    for participant in existing_detail.participants:
                        grouped.setdefault(participant.participant_type, []).append(participant.id)
                    current_participants = tuple(
                        ParticipantGroup(
                            participant_type=participant_type,
                            participant_ids=tuple(ids),
                        )
                        for participant_type, ids in grouped.items()
                    )

                self.meeting_repository.replace_relationships(
                    meeting.id,
                    current_related_type,
                    current_related_ids,
                    current_participants,
                )

            saved = self.meeting_repository.get_by_id(meeting.id)
            if saved is None:
                raise ValueError("Meeting not found after update.")

            new_values = {field: getattr(saved, field) for field in updateable_fields}
            changes = build_field_changes(old_values, new_values)
            changes = resolve_relationship_changes(
                changes,
                {
                    "host_id": lambda user_id: (
                        user.name
                        if (user := self.user_repository.get_by_id(user_id))
                        else None
                    ),
                },
            )

            updated_detail = self.meeting_repository.get_by_id_with_details(meeting.id)
            if updated_detail is None:
                raise ValueError("Meeting details could not be loaded after update.")

            relationship_changes = self._relationship_changes(
                existing_detail,
                updated_detail,
            )
            if relationship_changes:
                changes["relationships"] = relationship_changes

            if changes:
                change_summary_parts = []
                field_changes = {
                    key: value
                    for key, value in changes.items()
                    if key != "relationships"
                }
                if field_changes:
                    change_summary_parts.append(
                        format_field_changes(
                            field_changes,
                            field_labels={
                                "title": "Title",
                                "description": "Description",
                                "location": "Location",
                                "is_all_day": "All Day",
                                "start_at": "Start Time",
                                "end_at": "End Time",
                                "host_id": "Host",
                            },
                        )
                    )
                if relationship_changes:
                    change_summary_parts.append(self._format_relationship_changes(relationship_changes))

                self.timeline_recorder.record(
                    event_type="MEETING_UPDATED",
                    actor_id=current_user_id or saved.created_by_id,
                    message=(
                        f"Meeting {saved.title} was updated. "
                        f"Changes: {'; '.join(part for part in change_summary_parts if part)}"
                    ),
                    metadata={
                        "meeting_id": str(saved.id),
                        "title": saved.title,
                        "changes": changes,
                    },
                    targets=self._timeline_targets(updated_detail),
                )

            return saved

        return self.transaction_manager.execute(update)

    @staticmethod
    def _timeline_targets(detail) -> list[tuple[str, UUID]]:
        targets = [("MEETING", detail.meeting.id)]
        seen = {("MEETING", detail.meeting.id)}
        for related in detail.related_to:
            target = (related.record_type.value, related.id)
            if target not in seen:
                targets.append(target)
                seen.add(target)
        return targets

    @staticmethod
    def _relationship_snapshot(detail) -> dict:
        return {
            "related_to": [
                {
                    "type": item.record_type.value,
                    "id": str(item.id),
                    "name": item.name,
                }
                for item in detail.related_to
            ],
            "participants": [
                {
                    "type": item.participant_type.value,
                    "id": str(item.id),
                    "name": item.name,
                }
                for item in detail.participants
            ],
        }

    def _relationship_changes(self, old_detail, new_detail) -> dict | None:
        old_snapshot = self._relationship_snapshot(old_detail)
        new_snapshot = self._relationship_snapshot(new_detail)
        changes = {}
        for field in ("related_to", "participants"):
            if old_snapshot[field] != new_snapshot[field]:
                changes[field] = {
                    "old_value": old_snapshot[field],
                    "new_value": new_snapshot[field],
                }
        return changes or None

    @staticmethod
    def _format_relationship_changes(changes: dict) -> str:
        parts = []
        for field, change in changes.items():
            label = "Related To" if field == "related_to" else "Participants"
            old_value = change["old_value"]
            new_value = change["new_value"]
            old_display = ", ".join(
                f"{item['type']}: {item['name']}" for item in old_value
            ) or "None"
            new_display = ", ".join(
                f"{item['type']}: {item['name']}" for item in new_value
            ) or "None"
            parts.append(f"{label}: {old_display} → {new_display}")
        return "; ".join(parts)

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
