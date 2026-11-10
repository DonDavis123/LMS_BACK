from datetime import datetime, timedelta

from src.modules.calls.application.dto.mark_missed_calls import MarkMissedCallsResult
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.calls.domain.enums.call_status import CallStatus
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.timeline.application.services.change_tracker import (
    build_field_changes,
    format_field_changes,
)


class MarkMissedCallsUseCase:
    """Marks planned calls whose time has passed as Missed.

    A call stays Planned until someone logs it. Without this job a call
    scheduled last week would read as "Planned" forever. A grace period keeps
    a call that is only a little late from being marked while the owner is
    still about to log it. A Missed call stays editable, so it can still be
    logged as Completed afterwards.
    """

    GRACE_PERIOD = timedelta(hours=1)
    BATCH_LIMIT = 500

    FIELD_LABELS = {"status": "Status"}

    def __init__(
        self,
        call_repository: CallRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.call_repository = call_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, as_of: datetime) -> MarkMissedCallsResult:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("Missed-call processing time must be timezone-aware.")

        cutoff = as_of - self.GRACE_PERIOD
        marked = 0
        failures = 0

        overdue = self.call_repository.get_overdue_planned(
            started_before=cutoff,
            limit=self.BATCH_LIMIT,
        )

        for call in overdue:
            try:
                if self.transaction_manager.execute(
                    lambda call_id=call.id: self._mark_missed(call_id, cutoff)
                ):
                    marked += 1
            except ValueError:
                failures += 1

        return MarkMissedCallsResult(marked=marked, failures=failures)

    def _mark_missed(self, call_id, cutoff: datetime) -> bool:
        # Re-read inside the transaction: the owner may have logged or edited
        # the call since the overdue list was loaded, and that must win.
        call = self.call_repository.get_by_id(call_id)

        if (
            call is None
            or call.is_deleted
            or call.status != CallStatus.PLANNED
            or call.call_start_time > cutoff
        ):
            return False

        old_status = call.status
        call.mark_missed()
        saved = self.call_repository.save(call)

        changes = build_field_changes(
            {"status": old_status},
            {"status": saved.status},
        )

        targets = [("CALL", saved.id)]
        if saved.lead_id:
            targets.append(("LEAD", saved.lead_id))
        if saved.contact_id:
            targets.append(("CONTACT", saved.contact_id))
        if saved.account_id:
            targets.append(("ACCOUNT", saved.account_id))

        self.timeline_recorder.record(
            event_type="CALL_UPDATED",
            actor_id=saved.owner_id,
            message=(
                "Call was marked as missed because it was not logged by its "
                f"scheduled time. Changes: {format_field_changes(changes, field_labels=self.FIELD_LABELS)}"
            ),
            metadata={
                "call_id": str(saved.id),
                "changes": changes,
                "automatic": True,
            },
            targets=targets,
        )

        return True
