from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class UpdateReminderDTO:
    reminder_id: UUID
    fields: dict[str, Any]
