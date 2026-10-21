from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.calls.domain.enums.call_entry_method import CallEntryMethod
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType


@dataclass
class CreateCallDTO:
    created_by_id: UUID
    call_start_time: datetime
    outcome: CallOutcome
    owner_id: UUID | None = None
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    account_id: UUID | None = None
    call_type: CallType = CallType.OUTBOUND
    duration_seconds: int = 0
    description: str | None = None
    entry_method: CallEntryMethod = CallEntryMethod.MANUAL
