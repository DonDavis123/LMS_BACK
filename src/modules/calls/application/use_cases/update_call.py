from dataclasses import replace

from src.modules.calls.application.dto.update_call import UpdateCallDTO
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.timeline.application.services.change_tracker import (
    build_field_changes,
    format_field_changes,
)


class UpdateCallUseCase:
    NOT_LATEST_MESSAGE = (
        "Only the latest call can be updated. "
        "Earlier calls are kept as read-only history."
    )

    UPDATEABLE_FIELDS = (
        "call_start_time",
        "duration_seconds",
        "call_type",
        "outcome",
        "description",
    )

    IMMUTABLE_FIELDS = (
        "lead_id",
        "contact_id",
        "account_id",
        "created_by_id",
        "entry_method",
    )

    FIELD_LABELS = {
        "call_start_time": "Call Start Time",
        "duration_seconds": "Duration (seconds)",
        "call_type": "Call Type",
        "outcome": "Outcome",
        "description": "Description",
    }

    def __init__(
        self,
        call_repository: CallRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.call_repository = call_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, data: UpdateCallDTO, current_user_id=None):
        call = self.call_repository.get_by_id(data.call_id)

        if call is None:
            raise ValueError("Call not found.")

        if call.is_deleted:
            raise ValueError("Deleted Call cannot be updated.")

        # Once a newer call is logged on the same lead / contact, this one
        # becomes history and is frozen.
        if not self._is_latest_call(call):
            raise ValueError(self.NOT_LATEST_MESSAGE)

        fields = data.fields

        immutable = [
            field for field in self.IMMUTABLE_FIELDS
            if field in fields
        ]
        if immutable:
            raise ValueError(
                f"Call field(s) cannot be changed: {', '.join(immutable)}."
            )

        unsupported = [
            field for field in fields
            if field not in self.UPDATEABLE_FIELDS
        ]
        if unsupported:
            raise ValueError(
                f"Call field(s) cannot be updated: {', '.join(unsupported)}."
            )

        old_values = {
            field: getattr(call, field)
            for field in self.UPDATEABLE_FIELDS
        }

        def update():
            # Work on a copy so a failed validation never leaves a
            # half-modified entity behind.
            candidate = replace(call, **fields)
            candidate.validate()

            saved = self.call_repository.save(candidate)

            new_values = {
                field: getattr(saved, field)
                for field in self.UPDATEABLE_FIELDS
            }

            # Detect only actual changes (old and new values are kept).
            changes = build_field_changes(old_values, new_values)

            if changes:
                targets = [("CALL", saved.id)]

                if saved.lead_id:
                    targets.append(("LEAD", saved.lead_id))

                if saved.contact_id:
                    targets.append(("CONTACT", saved.contact_id))

                if saved.account_id:
                    targets.append(("ACCOUNT", saved.account_id))

                change_summary = format_field_changes(
                    changes,
                    field_labels=self.FIELD_LABELS,
                )

                self.timeline_recorder.record(
                    event_type="CALL_UPDATED",
                    actor_id=current_user_id or saved.owner_id,
                    message=f"Call was updated. Changes: {change_summary}",
                    metadata={
                        "call_id": str(saved.id),
                        "changes": changes,
                    },
                    targets=targets,
                )

            return saved

        return self.transaction_manager.execute(update)

    def _is_latest_call(self, call) -> bool:
        """True when ``call`` is the newest active call of its lead / contact.

        "Newest" uses the same ordering as the repository's related-record
        listing (call start time, then id, descending).
        """
        if call.lead_id is not None:
            record_filter = {"lead_id": call.lead_id}
        else:
            record_filter = {"contact_id": call.contact_id}

        newest = self.call_repository.get_by_related_record(
            limit=1,
            **record_filter,
        )

        return not newest or newest[0].call.id == call.id
