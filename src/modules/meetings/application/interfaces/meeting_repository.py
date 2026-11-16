from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.modules.meetings.application.dto.get_meeting import GetMeetingDTO
from src.modules.meetings.application.dto.get_meetings import GetMeetingsDTO
from src.modules.meetings.domain.entities.meeting import Meeting
from src.modules.meetings.domain.enums.meeting_participant_type import MeetingParticipantType
from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType
from src.modules.meetings.application.dto.participant_group import ParticipantGroup
from src.modules.meetings.application.dto.related_group import RelatedGroup
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class MeetingRepository(ABC):
    @abstractmethod
    def save(self, meeting: Meeting) -> Meeting:
        pass

    @abstractmethod
    def save_with_relationships(
        self,
        meeting: Meeting,
        related_groups: tuple[RelatedGroup, ...] = (),
        participant_groups: tuple[ParticipantGroup, ...] = (),
    ) -> Meeting:
        pass

    @abstractmethod
    def get_by_id(self, meeting_id: UUID) -> Meeting | None:
        pass

    @abstractmethod
    def get_by_id_with_details(self, meeting_id: UUID) -> GetMeetingDTO | None:
        pass

    @abstractmethod
    def get_all(self, query: ListQuery) -> PaginatedResult[GetMeetingsDTO]:
        pass

    @abstractmethod
    def get_by_start_at_range(self, start_at: datetime, end_at: datetime) -> list[Meeting]:
        """Return active meetings whose start_at is within the half-open range."""
        pass

    @abstractmethod
    def get_conference_meetings_not_ended(self, as_of: datetime) -> list[Meeting]:
        """Active meetings with a created Meet link that have not ended yet."""
        pass

    @abstractmethod
    def replace_relationships(
        self,
        meeting_id: UUID,
        related_groups: tuple[RelatedGroup, ...],
        participant_groups: tuple[ParticipantGroup, ...],
    ) -> None:
        pass

    @abstractmethod
    def soft_delete_by_id(self, meeting_id: UUID) -> Meeting | None:
        pass

    @abstractmethod
    def soft_delete_if_orphaned(
        self,
        record_type: MeetingRelatedRecordType,
        record_id: UUID,
    ) -> list[UUID]:
        pass

    @abstractmethod
    def transfer_host(
        self,
        from_user_id: UUID,
        to_user_id: UUID,
    ) -> int:
        """Reassign every Meeting hosted by ``from_user_id`` to ``to_user_id``.

        Meeting participants are not changed.
        """
        pass

    @abstractmethod
    def count_by_host_id(self, host_id: UUID) -> int:
        pass
