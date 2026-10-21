from dataclasses import replace

from src.modules.calls.application.dto.get_call_record import GetCallRecordDTO
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.timeline.application.interfaces.timeline_repository import (
    TimelineRepository,
)

CALL_EVENT_PREFIX = "CALL_"


class GetCallRecordsUseCase:
    """Calls table: one row per lead / contact, with its latest update."""

    def __init__(
        self,
        call_repository: CallRepository,
        timeline_repository: TimelineRepository,
    ):
        self.call_repository = call_repository
        self.timeline_repository = timeline_repository

    def execute(self, query: ListQuery) -> PaginatedResult[GetCallRecordDTO]:
        page = self.call_repository.get_record_summaries(query)

        lead_ids = [r.record_id for r in page.results if r.record_type == "LEAD"]
        contact_ids = [r.record_id for r in page.results if r.record_type == "CONTACT"]

        latest_updates = {}
        for entity_type, ids in (("LEAD", lead_ids), ("CONTACT", contact_ids)):
            if not ids:
                continue
            found = self.timeline_repository.get_latest_for_entities(
                entity_type,
                ids,
                event_type_prefix=CALL_EVENT_PREFIX,
            )
            for record_id, event in found.items():
                latest_updates[(entity_type, record_id)] = event

        return PaginatedResult(
            results=[
                replace(
                    row,
                    latest_update=latest_updates.get((row.record_type, row.record_id)),
                )
                for row in page.results
            ],
            page=page.page,
            page_size=page.page_size,
            total=page.total,
        )
