from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.tasks.domain.entities.task import Task


class TaskRepository(ABC):

    @abstractmethod
    def save(self, task: Task) -> Task:
        pass

    @abstractmethod
    def get_by_id(self, task_id: UUID) -> Task | None:
        pass

    @abstractmethod
    def get_all(self) -> list[Task]:
        pass
