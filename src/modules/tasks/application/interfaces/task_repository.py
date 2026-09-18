from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.tasks.domain.entities.task import Task
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class TaskRepository(ABC):

    @abstractmethod
    def save(self, task: Task) -> Task:
        pass

    @abstractmethod
    def get_by_id(self, task_id: UUID) -> Task | None:
        pass

    @abstractmethod
    def get_all(self, query: ListQuery) -> PaginatedResult[Task]:
        pass

    @abstractmethod
    def soft_delete_by_lead_id(self, lead_id: UUID) -> None:
        pass

    @abstractmethod
    def soft_delete_by_contact_id(self, contact_id: UUID) -> None:
        pass

    @abstractmethod
    def soft_delete_by_account_id(self, account_id: UUID) -> None:
        pass

    @abstractmethod
    def unlink_account_from_contact_tasks(self, account_id: UUID) -> None:
        pass
