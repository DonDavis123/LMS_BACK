from uuid import UUID

from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)
from src.modules.tasks.domain.entities.task import Task


class GetTaskUseCase:

    def __init__(
        self,
        task_repository: TaskRepository,
    ):
        self.task_repository = task_repository

    def execute(self, task_id: UUID) -> Task | None:
        task = self.task_repository.get_by_id(task_id)

        if task is None or task.is_deleted:
            return None

        return task
