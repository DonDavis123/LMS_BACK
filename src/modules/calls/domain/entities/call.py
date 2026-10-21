from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from ..enums.call_entry_method import CallEntryMethod
from ..enums.call_outcome import CallOutcome
from ..enums.call_type import CallType

MAX_DURATION_SECONDS = 86400
MAX_DESCRIPTION_LENGTH = 1000
FUTURE_TOLERANCE = timedelta(minutes=5)


@dataclass
class Call:
    id: UUID
    lead_id: UUID | None
    contact_id: UUID | None
    account_id: UUID | None
    owner_id: UUID
    call_type: CallType
    outcome: CallOutcome
    call_start_time: datetime
    duration_seconds: int
    description: str | None
    entry_method: CallEntryMethod
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    def soft_delete(self) -> None:
        if self.is_deleted:
            raise ValueError("Call is already deleted.")

        self.is_deleted = True

    def duration_label(self) -> str:
        """Human readable duration, e.g. ``4 min 10 sec``."""
        total = self.duration_seconds
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours} hr {minutes} min {seconds} sec"

        if minutes:
            return f"{minutes} min {seconds} sec"

        return f"{seconds} sec"

    def validate(self) -> None:
        """Validate the call and normalise its description.

        Used by ``create`` and re-used by the update use case so both paths
        enforce exactly the same rules. ``call_type``, ``outcome`` and
        ``entry_method`` given as plain strings are coerced to their enums.
        """
        if not self.owner_id:
            raise ValueError("Call owner is required.")

        if not self.created_by_id:
            raise ValueError("Call creator is required.")

        self.call_type = self._coerce_enum(CallType, self.call_type, "type")
        self.outcome = self._coerce_enum(CallOutcome, self.outcome, "outcome")
        self.entry_method = self._coerce_enum(
            CallEntryMethod,
            self.entry_method,
            "entry method",
        )

        if (self.lead_id is None) == (self.contact_id is None):
            raise ValueError(
                "Call must be associated with exactly one of a lead or a contact."
            )

        if self.account_id is not None and self.contact_id is None:
            raise ValueError("Call account requires an associated contact.")

        if self.call_start_time is None:
            raise ValueError("Call start time is required.")

        if not isinstance(self.call_start_time, datetime):
            raise ValueError("Call start time must be a datetime.")

        start = self.call_start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        if start > datetime.now(timezone.utc) + FUTURE_TOLERANCE:
            raise ValueError(
                "Call start time cannot be more than 5 minutes in the future."
            )

        if (
            isinstance(self.duration_seconds, bool)
            or not isinstance(self.duration_seconds, int)
        ):
            raise ValueError("Call duration must be a whole number of seconds.")

        if not 0 <= self.duration_seconds <= MAX_DURATION_SECONDS:
            raise ValueError(
                f"Call duration must be between 0 and {MAX_DURATION_SECONDS} seconds."
            )

        if self.description is not None:
            if not isinstance(self.description, str):
                raise ValueError("Call description must be a string.")

            self.description = self.description.strip() or None

        if (
            self.description is not None
            and len(self.description) > MAX_DESCRIPTION_LENGTH
        ):
            raise ValueError(
                f"Call description cannot exceed {MAX_DESCRIPTION_LENGTH} characters."
            )

    @staticmethod
    def _coerce_enum(enum_class, value, label: str):
        if isinstance(value, enum_class):
            return value

        try:
            return enum_class(value)
        except ValueError:
            raise ValueError(f"Invalid call {label}: {value!r}.")

    @classmethod
    def create(
        cls,
        owner_id: UUID,
        created_by_id: UUID,
        call_start_time: datetime,
        outcome: CallOutcome,
        lead_id: UUID | None = None,
        contact_id: UUID | None = None,
        account_id: UUID | None = None,
        call_type: CallType = CallType.OUTBOUND,
        duration_seconds: int = 0,
        description: str | None = None,
        entry_method: CallEntryMethod = CallEntryMethod.MANUAL,
    ) -> "Call":
        now = datetime.now(timezone.utc)

        call = cls(
            id=uuid4(),
            lead_id=lead_id,
            contact_id=contact_id,
            account_id=account_id,
            owner_id=owner_id,
            call_type=call_type,
            outcome=outcome,
            call_start_time=call_start_time,
            duration_seconds=duration_seconds,
            description=description,
            entry_method=entry_method,
            created_by_id=created_by_id,
            created_at=now,
            updated_at=now,
            is_deleted=False,
        )
        call.validate()

        return call
