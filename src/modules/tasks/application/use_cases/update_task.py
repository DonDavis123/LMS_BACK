from src.modules.accounts.application.interfaces.account_repository import AccountRepository
from src.modules.contacts.application.interfaces.contact_repository import ContactRepository
from src.modules.leads.application.interfaces.lead_repository import LeadRepository
from src.modules.tasks.application.dto.update_task import UpdateTaskDTO
from src.modules.tasks.application.interfaces.task_repository import TaskRepository
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.timeline.application.interfaces.timeline_recorder import TimelineRecorder
from src.modules.timeline.application.services.change_tracker import (
    build_field_changes,
    format_field_changes,
    resolve_relationship_changes,
)
from src.modules.shared.application.interfaces.transaction_manager import TransactionManager


class UpdateTaskUseCase:
    def __init__(
        self,
        task_repository: TaskRepository,
        user_repository: UserRepository,
        lead_repository: LeadRepository,
        contact_repository: ContactRepository,
        account_repository: AccountRepository,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.task_repository = task_repository
        self.user_repository = user_repository
        self.lead_repository = lead_repository
        self.contact_repository = contact_repository
        self.account_repository = account_repository
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, data: UpdateTaskDTO, current_user_id=None):
        task = self.task_repository.get_by_id(data.task_id)
        if task is None:
            raise ValueError("Task not found.")
        if task.is_deleted:
            raise ValueError("Deleted Task cannot be updated.")

        updateable_fields = (
            "subject", "due_date", "priority", "owner_id", "reminder_at",
            "lead_id", "contact_id", "account_id", "status", "description",
        )
        old_values = {field: getattr(task, field) for field in updateable_fields}
        fields = data.fields

        def update():
            if "owner_id" in fields:
                owner_id = fields["owner_id"]
                if owner_id is None:
                    raise ValueError("Task owner cannot be null.")
                owner = self.user_repository.get_by_id(owner_id)
                if owner is None:
                    raise ValueError("Task owner does not exist.")
                if not owner.is_active:
                    raise ValueError("Task owner is inactive.")
                if owner.role not in {UserRole.ADMIN, UserRole.SUPERADMIN}:
                    raise ValueError("Task owner must be an ADMIN or SUPERADMIN.")

            for field in updateable_fields:
                if field in fields:
                    setattr(task, field, fields[field])

            if not task.subject:
                raise ValueError("Task subject is required.")
            if task.lead_id is not None and task.contact_id is not None:
                raise ValueError("Task cannot be associated with both a lead and a contact.")
            if task.lead_id is not None and task.account_id is not None:
                raise ValueError("Task associated with a lead cannot have an account.")
            if task.account_id is not None and task.contact_id is None:
                raise ValueError("Task account requires an associated contact.")

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

            saved = self.task_repository.save(task)
            new_values = {field: getattr(saved, field) for field in updateable_fields}
            changes = build_field_changes(old_values, new_values)
            changes = resolve_relationship_changes(
                changes,
                {
                    "owner_id": lambda user_id: (
                        user.name
                        if (user := self.user_repository.get_by_id(user_id))
                        else None
                    ),
                    "lead_id": lambda lead_id: (
                        lead.name
                        if (lead := self.lead_repository.get_by_id(lead_id))
                        else None
                    ),
                    "contact_id": lambda contact_id: (
                        contact.name
                        if (contact := self.contact_repository.get_by_id(contact_id))
                        else None
                    ),
                    "account_id": lambda account_id: (
                        account.account_name
                        if (account := self.account_repository.get_by_id(account_id))
                        else None
                    ),
                },
            )

            if changes:
                targets = []
                if saved.lead_id:
                    targets.append(("LEAD", saved.lead_id))
                if saved.contact_id:
                    targets.append(("CONTACT", saved.contact_id))
                if saved.account_id:
                    targets.append(("ACCOUNT", saved.account_id))

                if targets:
                    change_summary = format_field_changes(
                        changes,
                        field_labels={
                            "subject": "Subject",
                            "due_date": "Due Date",
                            "priority": "Priority",
                            "owner_id": "Task Owner",
                            "reminder_at": "Reminder",
                            "lead_id": "Lead",
                            "contact_id": "Contact",
                            "account_id": "Account",
                            "status": "Status",
                            "description": "Description",
                        },
                    )
                    completed = (
                        "status" in changes
                        and changes["status"]["new_value"] == "Completed"
                        and changes["status"]["old_value"] != "Completed"
                    )
                    self.timeline_recorder.record(
                        event_type="TASK_COMPLETED" if completed else "TASK_UPDATED",
                        actor_id=current_user_id or saved.owner_id,
                        message=(
                            f"Task {saved.subject} was completed. "
                            f"Changes: {change_summary}"
                            if completed
                            else (
                                f"Task {saved.subject} was updated. "
                                f"Changes: {change_summary}"
                            )
                        ),
                        metadata={
                            "task_id": str(saved.id),
                            "subject": saved.subject,
                            "changes": changes,
                        },
                        targets=targets,
                    )
            return saved

        return self.transaction_manager.execute(update)
