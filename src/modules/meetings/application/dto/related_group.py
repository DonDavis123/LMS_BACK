from dataclasses import dataclass
from uuid import UUID

from src.modules.meetings.domain.enums.meeting_related_record_type import MeetingRelatedRecordType


@dataclass(frozen=True)
class RelatedGroup:
    """Related To records of one type (all leads, or all contacts).

    A Meeting can carry several groups, so it can be related to any number
    of leads and contacts at the same time.
    """

    record_type: MeetingRelatedRecordType
    record_ids: tuple[UUID, ...]
