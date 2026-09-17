from uuid import UUID

from src.modules.timeline.application.interfaces.timeline_repository import TimelineRepository


class GetTimelineUseCase:
    def __init__(self, timeline_repository: TimelineRepository):
        self.timeline_repository = timeline_repository

    def execute(self, entity_type: str, entity_id: UUID) -> list[dict]:
        normalized_type = entity_type.upper()
        if not self.timeline_repository.entity_exists(normalized_type, entity_id):
            raise ValueError("Timeline entity not found.")
        return self.timeline_repository.get_for_entity(normalized_type, entity_id)
