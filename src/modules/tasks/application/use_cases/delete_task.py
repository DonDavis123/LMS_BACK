from uuid import UUID

from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)


class DeleteTaskUseCase:

    def __init__(
        self,
        task_repository: TaskRepository,
    ):
        self.task_repository = task_repository

    def execute(self, task_id: UUID) -> None:
        task = self.task_repository.get_by_id(task_id)

        if task is None:
            raise ValueError("Task not found.")

        task.soft_delete()

        self.task_repository.save(task)
