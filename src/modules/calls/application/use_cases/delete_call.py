from uuid import UUID

from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder


class DeleteCallUseCase:

    def __init__(
        self,
        call_repository: CallRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.call_repository = call_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, call_id: UUID, current_user_id=None) -> None:
        call = self.call_repository.get_by_id(call_id)

        if call is None:
            raise ValueError("Call not found.")

        def deletion():
            targets = [("CALL", call.id)]

            if call.lead_id:
                targets.append(("LEAD", call.lead_id))
            if call.contact_id:
                targets.append(("CONTACT", call.contact_id))
            if call.account_id:
                targets.append(("ACCOUNT", call.account_id))

            call.soft_delete()
            self.call_repository.save(call)

            self.timeline_recorder.record(
                event_type="CALL_DELETED",
                actor_id=current_user_id or call.owner_id,
                message=(
                    f"Call deleted ({call.outcome.value}, "
                    f"{call.duration_label()})."
                ),
                metadata={
                    "call_id": str(call.id),
                    "outcome": call.outcome.value,
                    "duration_seconds": call.duration_seconds,
                },
                targets=targets,
            )

        self.transaction_manager.execute(deletion)
