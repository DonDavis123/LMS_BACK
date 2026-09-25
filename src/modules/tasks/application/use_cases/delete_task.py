from uuid import UUID

from src.modules.shared.application.interfaces.transaction_manager import TransactionManager
from src.modules.tasks.application.interfaces.task_repository import TaskRepository
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder


class DeleteTaskUseCase:

    def __init__(
        self,
        task_repository: TaskRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.task_repository = task_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, task_id: UUID, current_user_id=None) -> None:
        task = self.task_repository.get_by_id(task_id)

        if task is None:
            raise ValueError("Task not found.")

        def deletion():
            targets = [("TASK", task.id)]

            if task.lead_id:
                targets.append(("LEAD", task.lead_id))
            if task.contact_id:
                targets.append(("CONTACT", task.contact_id))
            if task.account_id:
                targets.append(("ACCOUNT", task.account_id))

            task.soft_delete()
            self.task_repository.save(task)

            self.timeline_recorder.record(
                event_type="TASK_DELETED",
                actor_id=current_user_id or task.owner_id,
                message=f"Task {task.subject} was deleted.",
                metadata={
                    "task_id": str(task.id),
                    "subject": task.subject,
                },
                targets=targets,
            )

        self.transaction_manager.execute(deletion)
