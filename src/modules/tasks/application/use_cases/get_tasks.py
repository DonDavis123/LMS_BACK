from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)
from src.modules.tasks.domain.entities.task import Task


class GetTasksUseCase:

    def __init__(
        self,
        task_repository: TaskRepository,
    ):
        self.task_repository = task_repository

    def execute(self) -> list[Task]:
        return self.task_repository.get_all()
