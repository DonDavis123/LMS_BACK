from uuid import UUID

from src.modules.deals.application.interfaces.deal_repository import DealRepository
from src.modules.deals.application.services.deal_timeline import clip, targets_for
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.timeline.application.interfaces.timeline_recorder import (
    TimelineRecorder,
)


class DeleteDealUseCase:

    def __init__(
        self,
        deal_repository: DealRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.deal_repository = deal_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, deal_id: UUID, current_user_id=None) -> None:
        deal = self.deal_repository.get_by_id(deal_id)

        if deal is None:
            raise ValueError("Deal not found.")

        def deletion():
            targets = targets_for(deal)

            deal.soft_delete()
            self.deal_repository.save(deal)

            self.timeline_recorder.record(
                event_type="DEAL_DELETED",
                actor_id=current_user_id or deal.owner_id,
                message=clip(f"Deal {deal.name} was deleted."),
                metadata={
                    "deal_id": str(deal.id),
                    "name": deal.name,
                },
                targets=targets,
            )

        self.transaction_manager.execute(deletion)
