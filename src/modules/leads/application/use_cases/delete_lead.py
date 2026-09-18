from uuid import UUID

from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)
from src.modules.timeline.application.interfaces.timeline_repository import (
    TimelineRepository,
)


class DeleteLeadUseCase:

    def __init__(
        self,
        lead_repository: LeadRepository,
        task_repository: TaskRepository,
        timeline_repository: TimelineRepository,
        transaction_manager: TransactionManager,
    ):
        self.lead_repository = lead_repository
        self.task_repository = task_repository
        self.timeline_repository = timeline_repository
        self.transaction_manager = transaction_manager

    def execute(self, lead_id: UUID) -> None:

        lead = self.lead_repository.get_by_id(lead_id)

        if lead is None:
            raise ValueError("Lead not found.")

        def deletion():

            # --------------------------------------------------
            # 1. Soft-delete Lead
            # --------------------------------------------------

            lead.soft_delete()

            self.lead_repository.save(lead)

            # --------------------------------------------------
            # 2. Soft-delete Tasks associated with the Lead
            # --------------------------------------------------

            self.task_repository.soft_delete_by_lead_id(
                lead_id,
            )

            # --------------------------------------------------
            # 3. Soft-delete Timeline events for the Lead
            # --------------------------------------------------

            self.timeline_repository.soft_delete_by_entity(
                "LEAD",
                lead_id,
            )

        self.transaction_manager.execute(
            deletion,
        )
