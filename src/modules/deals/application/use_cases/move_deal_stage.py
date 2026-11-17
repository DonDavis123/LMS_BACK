from src.modules.deals.application.dto.move_deal_stage import MoveDealStageDTO
from src.modules.deals.application.interfaces.deal_repository import DealRepository
from src.modules.deals.application.services.deal_timeline import (
    FIELD_LABELS,
    clip,
    record_stage_events,
    snapshot,
    targets_for,
)
from src.modules.deals.domain.entities.deal import Deal
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.timeline.application.interfaces.timeline_recorder import (
    TimelineRecorder,
)
from src.modules.timeline.application.services.change_tracker import (
    build_field_changes,
    format_field_changes,
)


class MoveDealStageUseCase:

    def __init__(
        self,
        deal_repository: DealRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.deal_repository = deal_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, data: MoveDealStageDTO, current_user_id=None) -> Deal:
        deal = self.deal_repository.get_by_id(data.deal_id)

        if deal is None:
            raise ValueError("Deal not found.")

        def move():
            from_stage = deal.stage
            old_values = snapshot(deal)

            # Stage rules (probability, closed_at, lost_reason) live in the
            # domain; it raises ValueError and leaves the deal untouched.
            deal.move_to_stage(
                data.stage,
                probability=data.probability,
                lost_reason=data.lost_reason,
            )

            saved = self.deal_repository.save(deal)
            actor_id = current_user_id or saved.owner_id

            if saved.stage is not from_stage:
                record_stage_events(
                    self.timeline_recorder, saved, from_stage, actor_id
                )
                return saved

            # Same stage: only a probability / lost reason change is possible.
            changes = build_field_changes(old_values, snapshot(saved))
            if changes:
                self.timeline_recorder.record(
                    event_type="DEAL_UPDATED",
                    actor_id=actor_id,
                    message=clip(
                        f"Deal {saved.name} was updated. Changes: "
                        f"{format_field_changes(changes, FIELD_LABELS)}"
                    ),
                    metadata={
                        "deal_id": str(saved.id),
                        "name": saved.name,
                        "changes": changes,
                    },
                    targets=targets_for(saved),
                )

            return saved

        return self.transaction_manager.execute(move)
