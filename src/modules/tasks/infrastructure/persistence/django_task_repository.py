from uuid import UUID

from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)
from src.modules.tasks.domain.entities.task import Task
from src.modules.tasks.domain.enums.task_priority import TaskPriority
from src.modules.tasks.domain.enums.task_status import TaskStatus

from .models import DjangoTaskModel


class DjangoTaskRepository(TaskRepository):

    def save(self, task: Task) -> Task:
        model, created = DjangoTaskModel.objects.update_or_create(
            id=task.id,
            defaults={
                "subject": task.subject,
                "due_date": task.due_date,
                "priority": task.priority.value,
                "owner_id": task.owner_id,
                "reminder_at": task.reminder_at,
                "lead_id": task.lead_id,
                "contact_id": task.contact_id,
                "account_id": task.account_id,
                "status": task.status.value,
                "description": task.description,
                "created_by_id": task.created_by_id,
                "is_deleted": task.is_deleted,
            },
        )

        return self._to_domain(model)

    def get_by_id(self, task_id: UUID) -> Task | None:
        try:
            model = DjangoTaskModel.objects.get(id=task_id)
        except DjangoTaskModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_all(self) -> list[Task]:
        models = DjangoTaskModel.objects.filter(is_deleted=False)

        return [
            self._to_domain(model)
            for model in models
        ]

    @staticmethod
    def _to_domain(model: DjangoTaskModel) -> Task:
        return Task(
            id=model.id,
            subject=model.subject,
            due_date=model.due_date,
            priority=TaskPriority(model.priority),
            owner_id=model.owner_id,
            reminder_at=model.reminder_at,
            lead_id=model.lead_id,
            contact_id=model.contact_id,
            account_id=model.account_id,
            status=TaskStatus(model.status),
            description=model.description,
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )
