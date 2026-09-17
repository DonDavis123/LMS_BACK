from dataclasses import dataclass
from uuid import UUID


@dataclass
class UpdateTaskDTO:
    task_id: UUID
    fields: dict[str, object]
