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
    @abstractmethod
    def soft_delete_by_entity(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        pass

    @abstractmethod
    def count_by_actor_id(self, actor_id: UUID) -> int:
        pass

    def get_latest_for_entities(
        self,
        entity_type: str,
        entity_ids: list[UUID],
        event_type_prefix: str | None = None,
    ) -> dict[UUID, dict]:
        """Newest active timeline event of each entity (``{entity_id: event}``).

        ``event_type_prefix`` limits the events considered (e.g. ``"CALL_"``).
        Entities without a matching event are left out. Not abstract so
        existing in-memory test doubles keep working.
        """
        raise NotImplementedError

    def get_targets_with_client_ref(
        self,
        *,
        event_type: str,
        client_ref: str,
        targets: list[tuple[str, UUID]],
    ) -> set[tuple[str, UUID]]:
        """The ``targets`` (``(entity_type, entity_id)``) that already have an
        active event of ``event_type`` whose ``metadata["client_ref"]`` equals
        ``client_ref``, in ONE query. Used to make a client action idempotent.
        Not abstract so existing in-memory test doubles keep working.
        """
        raise NotImplementedError
