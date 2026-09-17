from abc import ABC, abstractmethod
from uuid import UUID


class TimelineRecorder(ABC):
    @abstractmethod
    def record(
        self,
        *,
        event_type: str,
        actor_id: UUID,
        message: str,
        metadata: dict | None = None,
        targets: list[tuple[str, UUID]],
    ) -> None:
        pass
