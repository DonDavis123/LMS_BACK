from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID


class TimelineRepository(ABC):
    @abstractmethod
    def record(
        self,
        *,
        event_type: str,
        actor_id: UUID,
        message: str,
        metadata: dict,
        targets: list[tuple[str, UUID]],
        created_at: datetime | None = None,
    ) -> None:
        pass

    @abstractmethod
    def get_for_entity(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> list[dict]:
        pass

    @abstractmethod
    def entity_exists(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> bool:
        pass
