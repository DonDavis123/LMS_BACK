from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.tasks.application.dto.update_task import UpdateTaskDTO
from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole


class UpdateTaskUseCase:

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

    def execute(self, data: UpdateTaskDTO):
        task = self.task_repository.get_by_id(data.task_id)

        if task is None:
            raise ValueError("Task not found.")

        if task.is_deleted:
            raise ValueError("Deleted Task cannot be updated.")

        fields = data.fields

        if "owner_id" in fields:
            owner_id = fields["owner_id"]

            if owner_id is None:
                raise ValueError("Task owner cannot be null.")

            owner = self.user_repository.get_by_id(owner_id)

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

            task.owner_id = owner_id

        for field in {
            "subject",
            "due_date",
            "priority",
            "reminder_at",
            "lead_id",
            "contact_id",
            "account_id",
            "status",
            "description",
        }:
            if field in fields:
                setattr(task, field, fields[field])

        if not task.subject:
            raise ValueError("Task subject is required.")

        if task.lead_id is not None and task.contact_id is not None:
            raise ValueError(
                "Task cannot be associated with both a lead and a contact."
            )

        if task.lead_id is not None and task.account_id is not None:
            raise ValueError(
                "Task associated with a lead cannot have an account."
            )

        if task.account_id is not None and task.contact_id is None:
            raise ValueError(
                "Task account requires an associated contact."
            )

        if task.lead_id is not None:
            lead = self.lead_repository.get_by_id(task.lead_id)

            if lead is None or lead.is_deleted:
                raise ValueError("Selected lead not found.")

        if task.contact_id is not None:
            contact = self.contact_repository.get_by_id(task.contact_id)

            if contact is None or contact.is_deleted:
                raise ValueError("Selected contact not found.")

        if task.account_id is not None:
            account = self.account_repository.get_by_id(task.account_id)

            if account is None or account.is_deleted:
                raise ValueError("Selected account not found.")

        return self.task_repository.save(task)
