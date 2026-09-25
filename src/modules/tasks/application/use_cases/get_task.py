from uuid import UUID

from src.modules.tasks.application.dto.get_task import GetTaskDTO
from src.modules.tasks.application.interfaces.task_repository import TaskRepository


class GetTaskUseCase:

    def __init__(
        self,
        task_repository: TaskRepository,
    ):
        self.task_repository = task_repository

    def execute(self, task_id: UUID) -> GetTaskDTO | None:
        return self.task_repository.get_by_id_with_relations(task_id)
