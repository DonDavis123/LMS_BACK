from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.tasks.application.interfaces.task_repository import TaskRepository
from src.modules.tasks.domain.entities.task import Task


class GetTasksUseCase:

    def __init__(
        self,
        task_repository: TaskRepository,
    ):
        self.task_repository = task_repository

    def execute(self, query: ListQuery) -> PaginatedResult[Task]:
        return self.task_repository.get_all(query)
