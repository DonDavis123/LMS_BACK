from __future__ import annotations

from typing import Any, Mapping, Protocol
from uuid import UUID

from src.modules.email_activity.application.dto.log_email_compose import (
    ComposeEvent,
    ComposeTarget,
)
from src.modules.email_activity.application.interfaces.compose_log import ComposeLog
from src.modules.email_activity.domain.enums.record_type import RecordType


class TimelineRepositoryPort(Protocol):
    def get_targets_with_client_ref(
        self,
        *,
        event_type: str,
        client_ref: str,
        targets: list[tuple[str, UUID]],
    ) -> set[tuple[str, UUID]]: ...


class TimelineRecorderPort(Protocol):
    def record(
        self,
        *,
        event_type: str,
        actor_id: UUID,
        message: str,
        metadata: dict | None = None,
        targets: list[tuple[str, UUID]],
    ) -> None: ...


class TimelineComposeLog(ComposeLog):
    """``ComposeLog`` on top of the timeline module.

    ``event_type`` and ``entity_types`` (record type -> timeline entity type)
    are handed in by ``presentation/api/dependencies``, so the timeline's own
    enums stay the single source of truth.
    """

    def __init__(
        self,
        timeline_repository: TimelineRepositoryPort,
        timeline_recorder: TimelineRecorderPort,
        event_type: str,
        entity_types: Mapping[RecordType, str],
    ):
        self.timeline_repository = timeline_repository
        self.timeline_recorder = timeline_recorder
        self.event_type = event_type
        self.entity_types = entity_types

    def find_logged(
        self,
        targets: list[ComposeTarget],
        client_ref: str,
    ) -> set[ComposeTarget]:
        by_timeline_key = {self._key(target): target for target in targets}
        logged = self.timeline_repository.get_targets_with_client_ref(
            event_type=self.event_type,
            client_ref=client_ref,
            targets=list(by_timeline_key),
        )
        return {by_timeline_key[key] for key in logged if key in by_timeline_key}

    def record(self, events: list[ComposeEvent]) -> None:
        # One event per target: a record's timeline never shows the others.
        for event in events:
            self.timeline_recorder.record(
                event_type=self.event_type,
                actor_id=event.actor_id,
                message=event.message,
                metadata=event.metadata,
                targets=[self._key(event.target)],
            )

    def _key(self, target: ComposeTarget) -> tuple[str, UUID]:
        return (self.entity_types[target.record_type], target.record_id)
