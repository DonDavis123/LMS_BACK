from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction

from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.meetings.domain.enums.meeting_participant_type import (
    MeetingParticipantType,
)
from src.modules.meetings.domain.enums.meeting_related_record_type import (
    MeetingRelatedRecordType,
)

from .models import (
    DjangoMeetingModel,
    DjangoMeetingParticipantModel,
    DjangoMeetingRelatedRecordModel,
)


@dataclass(frozen=True)
class ParticipantGroup:
    participant_type: MeetingParticipantType
    participant_ids: tuple[UUID, ...]


class DjangoMeetingRepository:
    """Persistence implementation for the Meeting domain."""

    def save(self, meeting: Meeting) -> Meeting:
        model, _ = DjangoMeetingModel.objects.update_or_create(
            id=meeting.id,
            defaults={
                "title": meeting.title,
                "description": meeting.description,
                "location": meeting.location,
                "is_all_day": meeting.is_all_day,
                "start_at": meeting.start_at,
                "end_at": meeting.end_at,
                "host_id": meeting.host_id,
                "created_by_id": meeting.created_by_id,
                "is_deleted": meeting.is_deleted,
            },
        )
        return self._to_domain(model)

    def save_with_relationships(
        self,
        meeting: Meeting,
        related_record_type: MeetingRelatedRecordType | None = None,
        related_record_ids: tuple[UUID, ...] = (),
        participant_groups: tuple[ParticipantGroup, ...] = (),
    ) -> Meeting:
        """Atomically persist a Meeting and all supplied relationship rows."""
        with transaction.atomic():
            saved = self.save(meeting)

            if related_record_ids:
                if related_record_type is None:
                    raise ValueError(
                        "Related record type is required when related records are supplied."
                    )
                self._add_related_records_locked(
                    saved.id,
                    related_record_type,
                    related_record_ids,
                )

            for group in participant_groups:
                if group.participant_ids:
                    self._add_participants_locked(
                        saved.id,
                        group.participant_type,
                        group.participant_ids,
                    )

            return self._to_domain(
                DjangoMeetingModel.objects.get(id=saved.id)
            )

    def get_by_id(self, meeting_id: UUID) -> Meeting | None:
        try:
            model = DjangoMeetingModel.objects.get(
                id=meeting_id,
                is_deleted=False,
            )
        except DjangoMeetingModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def soft_delete_by_id(self, meeting_id: UUID) -> Meeting | None:
        with transaction.atomic():
            try:
                model = (
                    DjangoMeetingModel.objects
                    .select_for_update()
                    .get(id=meeting_id, is_deleted=False)
                )
            except DjangoMeetingModel.DoesNotExist:
                return None

            meeting = self._to_domain(model)
            meeting.soft_delete()
            model.is_deleted = True
            model.save(update_fields=["is_deleted", "updated_at"])
            return self._to_domain(model)

    def add_related_records(
        self,
        meeting_id: UUID,
        record_type: MeetingRelatedRecordType,
        record_ids: tuple[UUID, ...],
    ) -> None:
        with transaction.atomic():
            self._add_related_records_locked(
                meeting_id,
                record_type,
                record_ids,
            )

    def add_participants(
        self,
        meeting_id: UUID,
        participant_type: MeetingParticipantType,
        participant_ids: tuple[UUID, ...],
    ) -> None:
        with transaction.atomic():
            self._add_participants_locked(
                meeting_id,
                participant_type,
                participant_ids,
            )

    def _add_related_records_locked(
        self,
        meeting_id: UUID,
        record_type: MeetingRelatedRecordType,
        record_ids: tuple[UUID, ...],
    ) -> None:
        self._lock_active_meeting(meeting_id)
        self._validate_unique_ids(record_ids, "related records")

        existing_types = set(
            DjangoMeetingRelatedRecordModel.objects
            .filter(meeting_id=meeting_id)
            .values_list("record_type", flat=True)
        )

        if existing_types and existing_types != {record_type.value}:
            raise ValueError(
                "A Meeting cannot have both Lead and Contact Related To records."
            )

        rows = []
        for record_id in record_ids:
            if record_type == MeetingRelatedRecordType.LEAD:
                rows.append(
                    DjangoMeetingRelatedRecordModel(
                        meeting_id=meeting_id,
                        record_type=record_type.value,
                        lead_id=record_id,
                    )
                )
            elif record_type == MeetingRelatedRecordType.CONTACT:
                rows.append(
                    DjangoMeetingRelatedRecordModel(
                        meeting_id=meeting_id,
                        record_type=record_type.value,
                        contact_id=record_id,
                    )
                )
            else:
                raise ValueError(f"Unsupported related record type: {record_type}.")

        try:
            DjangoMeetingRelatedRecordModel.objects.bulk_create(rows)
        except IntegrityError as exc:
            raise ValueError("Duplicate or invalid Meeting Related To record.") from exc

    def _add_participants_locked(
        self,
        meeting_id: UUID,
        participant_type: MeetingParticipantType,
        participant_ids: tuple[UUID, ...],
    ) -> None:
        self._lock_active_meeting(meeting_id)
        self._validate_unique_ids(participant_ids, "participants")

        rows = []
        for participant_id in participant_ids:
            if participant_type == MeetingParticipantType.LEAD:
                rows.append(
                    DjangoMeetingParticipantModel(
                        meeting_id=meeting_id,
                        participant_type=participant_type.value,
                        lead_id=participant_id,
                    )
                )
            elif participant_type == MeetingParticipantType.USER:
                rows.append(
                    DjangoMeetingParticipantModel(
                        meeting_id=meeting_id,
                        participant_type=participant_type.value,
                        user_id=participant_id,
                    )
                )
            elif participant_type == MeetingParticipantType.CONTACT:
                rows.append(
                    DjangoMeetingParticipantModel(
                        meeting_id=meeting_id,
                        participant_type=participant_type.value,
                        contact_id=participant_id,
                    )
                )
            else:
                raise ValueError(f"Unsupported participant type: {participant_type}.")

        try:
            DjangoMeetingParticipantModel.objects.bulk_create(rows)
        except IntegrityError as exc:
            raise ValueError("Duplicate or invalid Meeting participant.") from exc

    @staticmethod
    def _lock_active_meeting(meeting_id: UUID) -> DjangoMeetingModel:
        try:
            return (
                DjangoMeetingModel.objects
                .select_for_update()
                .get(id=meeting_id, is_deleted=False)
            )
        except DjangoMeetingModel.DoesNotExist as exc:
            raise ValueError("Active Meeting was not found.") from exc

    @staticmethod
    def _validate_unique_ids(
        record_ids: tuple[UUID, ...],
        label: str,
    ) -> None:
        if len(record_ids) != len(set(record_ids)):
            raise ValueError(f"Duplicate {label} are not allowed.")

    @staticmethod
    def _to_domain(model: DjangoMeetingModel) -> Meeting:
        return Meeting(
            id=model.id,
            title=model.title,
            description=model.description,
            location=model.location,
            is_all_day=model.is_all_day,
            start_at=model.start_at,
            end_at=model.end_at,
            host_id=model.host_id,
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )
