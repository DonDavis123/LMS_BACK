from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.tasks.application.dto.get_task import GetTaskDTO
from src.modules.tasks.application.interfaces.task_repository import TaskRepository


class GetTasksUseCase:

    def __init__(
        self,
        task_repository: TaskRepository,
    ):
        self.task_repository = task_repository

    def execute(self, query: ListQuery) -> PaginatedResult[GetTaskDTO]:
        return self.task_repository.get_all_with_relations(query)
