from uuid import UUID

from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.timeline.application.interfaces.timeline_repository import TimelineRepository


class DefaultTimelineRecorder(TimelineRecorder):
    def __init__(self, repository: TimelineRepository):
        self.repository = repository

    def record(
        self,
        *,
        event_type: str,
        actor_id: UUID,
        message: str,
        metadata: dict | None = None,
        targets: list[tuple[str, UUID]],
    ) -> None:
        if not targets:
            raise ValueError("Timeline event requires at least one target.")
        self.repository.record(
            event_type=event_type,
            actor_id=actor_id,
            message=message,
            metadata=metadata or {},
            targets=targets,
        )
