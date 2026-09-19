from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from src.modules.meetings.application.dto.get_meeting import (
    GetMeetingDTO,
    MeetingParticipantDTO,
    MeetingRelatedRecordDTO,
)
from src.modules.meetings.application.dto.get_meetings import GetMeetingsDTO
from src.modules.meetings.application.dto.participant_group import ParticipantGroup
from src.modules.meetings.application.interfaces.meeting_repository import MeetingRepository
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult

from .models import (
    DjangoMeetingModel,
    DjangoMeetingParticipantModel,
    DjangoMeetingRelatedRecordModel,
)


class DjangoMeetingRepository(MeetingRepository):
    """Django persistence implementation of the Meeting repository contract."""

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
        with transaction.atomic():
            saved = self.save(meeting)
            self._replace_relationships_locked(
                saved.id, related_record_type, related_record_ids, participant_groups,
            )
            return self._to_domain(DjangoMeetingModel.objects.get(id=saved.id))

    def get_by_id(self, meeting_id: UUID) -> Meeting | None:
        try:
            model = DjangoMeetingModel.objects.get(id=meeting_id, is_deleted=False)
        except DjangoMeetingModel.DoesNotExist:
            return None
        return self._to_domain(model)

    def get_by_id_with_details(self, meeting_id: UUID) -> GetMeetingDTO | None:
        try:
            model = (
                DjangoMeetingModel.objects
                .select_related("host", "created_by")
                .get(id=meeting_id, is_deleted=False)
            )
        except DjangoMeetingModel.DoesNotExist:
            return None

        related_rows = (
            DjangoMeetingRelatedRecordModel.objects
            .filter(meeting_id=meeting_id)
            .filter(
                Q(lead__isnull=True) | Q(lead__is_deleted=False)
            )
            .filter(
                Q(contact__isnull=True) | Q(contact__is_deleted=False)
            )
            .select_related("lead", "contact")
            .order_by("id")
        )
        participant_rows = (
            DjangoMeetingParticipantModel.objects
            .filter(meeting_id=meeting_id)
            .select_related("lead", "contact", "user")
            .order_by("id")
        )

        related = []
        for row in related_rows:
            if row.record_type == MeetingRelatedRecordType.LEAD.value and row.lead:
                related.append(MeetingRelatedRecordDTO(row.lead_id, MeetingRelatedRecordType.LEAD, row.lead.name))
            elif row.record_type == MeetingRelatedRecordType.CONTACT.value and row.contact:
                related.append(MeetingRelatedRecordDTO(row.contact_id, MeetingRelatedRecordType.CONTACT, row.contact.name))

        participants = []
        for row in participant_rows:
            if row.participant_type == MeetingParticipantType.LEAD.value and row.lead:
                participants.append(MeetingParticipantDTO(row.lead_id, MeetingParticipantType.LEAD, row.lead.name))
            elif row.participant_type == MeetingParticipantType.CONTACT.value and row.contact:
                participants.append(MeetingParticipantDTO(row.contact_id, MeetingParticipantType.CONTACT, row.contact.name))
            elif row.participant_type == MeetingParticipantType.USER.value and row.user:
                participants.append(MeetingParticipantDTO(row.user_id, MeetingParticipantType.USER, row.user.name))

        return GetMeetingDTO(
            meeting=self._to_domain(model),
            host_id=model.host_id,
            host_name=model.host.name,
            created_by_id=model.created_by_id,
            created_by_name=model.created_by.name,
            related_to=tuple(related),
            participants=tuple(participants),
        )

    def get_all(self, query: ListQuery) -> PaginatedResult[GetMeetingsDTO]:
        queryset = (
            DjangoMeetingModel.objects
            .select_related("host")
            .filter(is_deleted=False)
            .order_by("start_at", "id")
        )
        total = queryset.count()
        offset = (query.page - 1) * query.page_size
        models = list(queryset[offset:offset + query.page_size])
        meeting_ids = [model.id for model in models]

        related_by_meeting: dict[UUID, list[tuple[MeetingRelatedRecordType, str]]] = {meeting_id: [] for meeting_id in meeting_ids}
        if meeting_ids:
            rows = (
                DjangoMeetingRelatedRecordModel.objects
                .filter(meeting_id__in=meeting_ids)
                .filter(Q(lead__isnull=True) | Q(lead__is_deleted=False))
                .filter(Q(contact__isnull=True) | Q(contact__is_deleted=False))
                .select_related("lead", "contact")
                .order_by("id")
            )
            for row in rows:
                if row.record_type == MeetingRelatedRecordType.LEAD.value and row.lead:
                    related_by_meeting[row.meeting_id].append((MeetingRelatedRecordType.LEAD, row.lead.name))
                elif row.record_type == MeetingRelatedRecordType.CONTACT.value and row.contact:
                    related_by_meeting[row.meeting_id].append((MeetingRelatedRecordType.CONTACT, row.contact.name))

        contacts_by_meeting: dict[UUID, list[str]] = {meeting_id: [] for meeting_id in meeting_ids}
        if meeting_ids:
            rows = (
                DjangoMeetingParticipantModel.objects
                .filter(meeting_id__in=meeting_ids, participant_type=MeetingParticipantType.CONTACT.value, contact__is_deleted=False)
                .select_related("contact")
                .order_by("id")
            )
            for row in rows:
                if row.contact:
                    contacts_by_meeting[row.meeting_id].append(row.contact.name)

        results = []
        for model in models:
            related = related_by_meeting[model.id]
            related_type = related[0][0] if related else None
            related_contact_names = [
                name for item_type, name in related
                if item_type == MeetingRelatedRecordType.CONTACT
            ]
            contact_names = tuple(dict.fromkeys(related_contact_names + contacts_by_meeting[model.id]))
            results.append(
                GetMeetingsDTO(
                    id=model.id,
                    title=model.title,
                    start_at=model.start_at,
                    end_at=model.end_at,
                    related_to_type=related_type,
                    related_to_names=tuple(name for _, name in related),
                    contact_names=contact_names,
                    host_id=model.host_id,
                    host_name=model.host.name,
                )
            )

        return PaginatedResult(results=results, page=query.page, page_size=query.page_size, total=total)

    def replace_relationships(
        self,
        meeting_id: UUID,
        related_record_type: MeetingRelatedRecordType | None,
        related_record_ids: tuple[UUID, ...],
        participant_groups: tuple[ParticipantGroup, ...],
    ) -> None:
        with transaction.atomic():
            self._lock_active_meeting(meeting_id)
            self._replace_relationships_locked(
                meeting_id, related_record_type, related_record_ids, participant_groups,
            )

    def soft_delete_by_id(self, meeting_id: UUID) -> Meeting | None:
        with transaction.atomic():
            try:
                model = DjangoMeetingModel.objects.select_for_update().get(id=meeting_id, is_deleted=False)
            except DjangoMeetingModel.DoesNotExist:
                return None
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
            self._add_related_records_locked(meeting_id, record_type, record_ids)

    def add_participants(
        self,
        meeting_id: UUID,
        participant_type: MeetingParticipantType,
        participant_ids: tuple[UUID, ...],
    ) -> None:
        with transaction.atomic():
            self._add_participants_locked(meeting_id, participant_type, participant_ids)

    def soft_delete_if_orphaned(
        self,
        record_type: MeetingRelatedRecordType,
        record_id: UUID,
    ) -> list[UUID]:
        if record_type not in {MeetingRelatedRecordType.LEAD, MeetingRelatedRecordType.CONTACT}:
            raise ValueError("Only Lead or Contact records can trigger Meeting orphan cleanup.")

        with transaction.atomic():
            field = "lead_id" if record_type == MeetingRelatedRecordType.LEAD else "contact_id"
            candidate_ids = list(
                DjangoMeetingRelatedRecordModel.objects
                .filter(record_type=record_type.value, **{field: record_id})
                .values_list("meeting_id", flat=True)
                .distinct()
            )
            deleted_ids: list[UUID] = []
            for meeting_id in candidate_ids:
                active_related = DjangoMeetingRelatedRecordModel.objects.filter(
                    meeting_id=meeting_id, record_type=record_type.value
                )
                if not active_related.exists():
                    continue
                # Only rows pointing to currently active Lead/Contact records count.
                if record_type == MeetingRelatedRecordType.LEAD:
                    active_exists = active_related.filter(lead__is_deleted=False).exists()
                else:
                    active_exists = active_related.filter(contact__is_deleted=False).exists()
                if active_exists:
                    continue
                updated = DjangoMeetingModel.objects.filter(id=meeting_id, is_deleted=False).update(is_deleted=True)
                if updated:
                    deleted_ids.append(meeting_id)
            return deleted_ids

    def _replace_relationships_locked(
        self,
        meeting_id: UUID,
        related_record_type: MeetingRelatedRecordType | None,
        related_record_ids: tuple[UUID, ...],
        participant_groups: tuple[ParticipantGroup, ...],
    ) -> None:
        self._lock_active_meeting(meeting_id)
        if related_record_ids and related_record_type is None:
            raise ValueError("Related record type is required when related records are supplied.")
        if len(related_record_ids) != len(set(related_record_ids)):
            raise ValueError("Duplicate related records are not allowed.")

        self._validate_participant_groups(participant_groups)
        DjangoMeetingRelatedRecordModel.objects.filter(meeting_id=meeting_id).delete()
        DjangoMeetingParticipantModel.objects.filter(meeting_id=meeting_id).delete()

        if related_record_ids:
            self._add_related_records_locked(meeting_id, related_record_type, related_record_ids)
        for group in participant_groups:
            if group.participant_ids:
                self._add_participants_locked(meeting_id, group.participant_type, group.participant_ids)

    @staticmethod
    def _validate_participant_groups(groups: tuple[ParticipantGroup, ...]) -> None:
        seen: set[UUID] = set()
        for group in groups:
            if len(group.participant_ids) != len(set(group.participant_ids)):
                raise ValueError("Duplicate participants are not allowed.")
            for participant_id in group.participant_ids:
                if participant_id in seen:
                    raise ValueError("The same participant cannot be added more than once.")
                seen.add(participant_id)

    def _add_related_records_locked(self, meeting_id, record_type, record_ids):
        self._lock_active_meeting(meeting_id)
        self._validate_unique_ids(record_ids, "related records")
        existing_types = set(DjangoMeetingRelatedRecordModel.objects.filter(meeting_id=meeting_id).values_list("record_type", flat=True))
        if existing_types and existing_types != {record_type.value}:
            raise ValueError("A Meeting cannot have both Lead and Contact Related To records.")
        rows = []
        for record_id in record_ids:
            if record_type == MeetingRelatedRecordType.LEAD:
                rows.append(DjangoMeetingRelatedRecordModel(meeting_id=meeting_id, record_type=record_type.value, lead_id=record_id))
            elif record_type == MeetingRelatedRecordType.CONTACT:
                rows.append(DjangoMeetingRelatedRecordModel(meeting_id=meeting_id, record_type=record_type.value, contact_id=record_id))
            else:
                raise ValueError(f"Unsupported related record type: {record_type}.")
        try:
            DjangoMeetingRelatedRecordModel.objects.bulk_create(rows)
        except IntegrityError as exc:
            raise ValueError("Duplicate or invalid Meeting Related To record.") from exc

    def _add_participants_locked(self, meeting_id, participant_type, participant_ids):
        self._lock_active_meeting(meeting_id)
        self._validate_unique_ids(participant_ids, "participants")
        rows = []
        for participant_id in participant_ids:
            if participant_type == MeetingParticipantType.LEAD:
                rows.append(DjangoMeetingParticipantModel(meeting_id=meeting_id, participant_type=participant_type.value, lead_id=participant_id))
            elif participant_type == MeetingParticipantType.USER:
                rows.append(DjangoMeetingParticipantModel(meeting_id=meeting_id, participant_type=participant_type.value, user_id=participant_id))
            elif participant_type == MeetingParticipantType.CONTACT:
                rows.append(DjangoMeetingParticipantModel(meeting_id=meeting_id, participant_type=participant_type.value, contact_id=participant_id))
            else:
                raise ValueError(f"Unsupported participant type: {participant_type}.")
        try:
            DjangoMeetingParticipantModel.objects.bulk_create(rows)
        except IntegrityError as exc:
            raise ValueError("Duplicate or invalid Meeting participant.") from exc

    @staticmethod
    def _validate_unique_ids(
        record_ids: tuple[UUID, ...],
        label: str,
    ) -> None:
        if len(record_ids) != len(set(record_ids)):
            raise ValueError(f"Duplicate {label} are not allowed.")

    @staticmethod
    def _lock_active_meeting(meeting_id: UUID) -> DjangoMeetingModel:
        try:
            return DjangoMeetingModel.objects.select_for_update().get(id=meeting_id, is_deleted=False)
        except DjangoMeetingModel.DoesNotExist as exc:
            raise ValueError("Active Meeting was not found.") from exc

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
