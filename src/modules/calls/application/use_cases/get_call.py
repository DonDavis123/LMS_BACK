from uuid import UUID

from src.modules.calls.application.dto.get_call_detail import GetCallDetailDTO
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.timeline.application.interfaces.timeline_repository import (
    TimelineRepository,
)

RELATED_CALLS_LIMIT = 50


class GetCallDetailUseCase:

    def __init__(
        self,
        call_repository: CallRepository,
        timeline_repository: TimelineRepository,
    ):
        self.call_repository = call_repository
        self.timeline_repository = timeline_repository

    def execute(self, call_id: UUID) -> GetCallDetailDTO | None:
        call_dto = self.call_repository.get_by_id_with_relations(call_id)

        if call_dto is None or call_dto.call.is_deleted:
            return None

        call = call_dto.call

        if call.lead_id is not None:
            related_record_type = "LEAD"
            related_record_id = call.lead_id
            related_record_name = call_dto.lead_name
            record_filter = {"lead_id": call.lead_id}
        else:
            related_record_type = "CONTACT"
            related_record_id = call.contact_id
            related_record_name = call_dto.contact_name
            record_filter = {"contact_id": call.contact_id}

        # Includes the CALL_LOGGED event and every CALL_UPDATED event with
        # its old/new values.
        change_history = self.timeline_repository.get_for_entity("CALL", call.id)

        related_calls = self.call_repository.get_by_related_record(
            exclude_call_id=call.id,
            limit=RELATED_CALLS_LIMIT,
            **record_filter,
        )

        total_calls_for_record = self.call_repository.count_by_related_record(
            **record_filter,
        )

        # ``related_calls`` is newest first, so its head is the newest OTHER
        # call; this call is the latest unless that one sorts after it
        # (same ordering as the repository: start time, then id).
        is_latest = not related_calls or (
            (call.call_start_time, call.id)
            > (related_calls[0].call.call_start_time, related_calls[0].call.id)
        )

        return GetCallDetailDTO(
            call=call_dto,
            related_record_type=related_record_type,
            related_record_id=related_record_id,
            related_record_name=related_record_name,
            change_history=change_history,
            related_calls=related_calls,
            total_calls_for_record=total_calls_for_record,
            is_latest=is_latest,
        )
