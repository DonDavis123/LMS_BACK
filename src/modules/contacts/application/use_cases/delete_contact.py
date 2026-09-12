from uuid import UUID

from src.modules.contacts.application.dto.delete_contact import DeleteContactDTO
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)


class DeleteContactUseCase:
    def __init__(
        self,
        contact_repository: ContactRepository,
    ):
        self.contact_repository = contact_repository

    def execute(
        self,
        data: DeleteContactDTO,
    ):
        contact = self.contact_repository.get_by_id(
            data.contact_id,
        )

        if contact is None:
            raise ValueError("Contact not found.")

        contact.is_deleted = True

        # A deleted Contact should no longer belong to an Account.
        contact.account_id = None

        return self.contact_repository.save(contact)