from dataclasses import dataclass
from uuid import UUID

from src.modules.tasks.domain.entities.task import Task


@dataclass(frozen=True)
class GetTaskDTO:
    """Application read model for task detail/list responses.

    The domain Task keeps only relationship IDs. This DTO adds display names
    required by the presentation layer without polluting the domain entity
    with persistence-specific concerns.
    """

    task: Task
    lead_name: str | None
    contact_name: str | None
    account_name: str | None
