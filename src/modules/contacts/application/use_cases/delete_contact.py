from uuid import UUID

from src.modules.contacts.application.dto.delete_contact import DeleteContactDTO
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)


class DeleteContactUseCase:
    def __init__(
        self,
        contact_repository: ContactRepository,
        task_repository: TaskRepository,
        transaction_manager: TransactionManager,
    ):
        self.contact_repository = contact_repository
        self.task_repository = task_repository
        self.transaction_manager = transaction_manager

    def execute(
        self,
        data: DeleteContactDTO,
    ):
        contact = self.contact_repository.get_by_id(
            data.contact_id,
        )

        if contact is None:
            raise ValueError("Contact not found.")

        def deletion():

            contact.is_deleted = True

            # A deleted Contact should no longer belong to an Account.
            contact.account_id = None

            saved_contact = self.contact_repository.save(contact)

            # --------------------------------------------------
            # Soft-delete Tasks associated with the Contact
            # --------------------------------------------------

            self.task_repository.soft_delete_by_contact_id(
                data.contact_id,
            )

            return saved_contact

        return self.transaction_manager.execute(
            deletion,
        )
