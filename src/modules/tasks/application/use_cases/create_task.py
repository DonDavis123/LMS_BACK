from src.modules.tasks.application.dto.create_task import CreateTaskDTO
from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)
from src.modules.tasks.domain.entities.task import Task
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole


class CreateTaskUseCase:

    def __init__(
        self,
        task_repository: TaskRepository,
        user_repository: UserRepository,
        lead_repository: LeadRepository,
        contact_repository: ContactRepository,
        account_repository: AccountRepository,
    ):
        self.task_repository = task_repository
        self.user_repository = user_repository
        self.lead_repository = lead_repository
        self.contact_repository = contact_repository
        self.account_repository = account_repository

    def execute(
        self,
        data: CreateTaskDTO,
    ) -> Task:
        if not data.subject:
            raise ValueError("Task subject is required.")

        if data.owner_id is None:
            raise ValueError("Task owner is required.")

        if data.created_by_id is None:
            raise ValueError("Task creator is required.")

        owner = self.user_repository.get_by_id(data.owner_id)

        if owner is None:
            raise ValueError("Task owner does not exist.")

        if not owner.is_active:
            raise ValueError("Task owner is inactive.")

        if owner.role not in {
            UserRole.ADMIN,
            UserRole.SUPERADMIN,
        }:
            raise ValueError(
                "Task owner must be an ADMIN or SUPERADMIN."
            )

        creator = self.user_repository.get_by_id(data.created_by_id)

        if creator is None:
            raise ValueError("Task creator does not exist.")

        if not creator.is_active:
            raise ValueError("Task creator is inactive.")

        if data.lead_id is not None and data.contact_id is not None:
            raise ValueError(
                "Task cannot be associated with both a lead and a contact."
            )

        if data.lead_id is not None and data.account_id is not None:
            raise ValueError(
                "Task associated with a lead cannot have an account."
            )

        if data.account_id is not None and data.contact_id is None:
            raise ValueError(
                "Task account requires an associated contact."
            )

        if data.lead_id is not None:
            lead = self.lead_repository.get_by_id(data.lead_id)

            if lead is None or lead.is_deleted:
                raise ValueError("Selected lead not found.")

        if data.contact_id is not None:
            contact = self.contact_repository.get_by_id(data.contact_id)

            if contact is None or contact.is_deleted:
                raise ValueError("Selected contact not found.")

        if data.account_id is not None:
            account = self.account_repository.get_by_id(data.account_id)

            if account is None or account.is_deleted:
                raise ValueError("Selected account not found.")

        task = Task.create(
            subject=data.subject,
            owner_id=data.owner_id,
            created_by_id=data.created_by_id,
            due_date=data.due_date,
            priority=data.priority,
            reminder_at=data.reminder_at,
            lead_id=data.lead_id,
            contact_id=data.contact_id,
            account_id=data.account_id,
            status=data.status,
            description=data.description,
        )

        return self.task_repository.save(task)
