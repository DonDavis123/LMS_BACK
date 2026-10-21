from uuid import UUID

from src.modules.calls.application.dto.get_call_record_history import (
    GetCallRecordHistoryDTO,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.calls.application.services.call_history import (
    SNAPSHOT_FIELDS,
    build_record_history,
)
from src.modules.timeline.application.interfaces.timeline_repository import (
    TimelineRepository,
)

HISTORY_CALL_LIMIT = 500


class GetCallRecordHistoryUseCase:
    """Detailed history of every call on the lead/contact of one call."""

    def __init__(
        self,
        call_repository: CallRepository,
        timeline_repository: TimelineRepository,
    ):
        self.call_repository = call_repository
        self.timeline_repository = timeline_repository

    def execute(self, call_id: UUID) -> GetCallRecordHistoryDTO | None:
        call_dto = self.call_repository.get_by_id_with_relations(call_id)

        if call_dto is None or call_dto.call.is_deleted:
            return None

        call = call_dto.call

        if call.lead_id is not None:
            record_type = "LEAD"
            record_id = call.lead_id
            record_name = call_dto.lead_name
            record_filter = {"lead_id": call.lead_id}
        else:
            record_type = "CONTACT"
            record_id = call.contact_id
            record_name = call_dto.contact_name
            record_filter = {"contact_id": call.contact_id}

        record_calls = self.call_repository.get_by_related_record(
            limit=HISTORY_CALL_LIMIT,
            **record_filter,
        )

        live_calls = {}
        for item in record_calls:
            state = {
                field: getattr(item.call, field).value
                if field in ("call_type", "outcome")
                else getattr(item.call, field)
                for field in SNAPSHOT_FIELDS
            }
            state["owner_name"] = item.owner_name
            live_calls[str(item.call.id)] = state

        events = self.timeline_repository.get_for_entity(record_type, record_id)

        return GetCallRecordHistoryDTO(
            related_record_type=record_type,
            related_record_id=record_id,
            related_record_name=record_name,
            total_calls_for_record=len(record_calls),
            events=build_record_history(events, live_calls),
        )
