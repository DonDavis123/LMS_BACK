"""Business-rule checks shared by the create and update use cases."""
from uuid import UUID

from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole


def validate_owner(user_repository: UserRepository, owner_id: UUID | None) -> None:
    if owner_id is None:
        raise ValueError("Deal owner is required.")

    owner = user_repository.get_by_id(owner_id)

    if owner is None or owner.is_deleted:
        raise ValueError("Deal owner does not exist.")

    if not owner.is_active:
        raise ValueError("Deal owner is inactive.")

    if owner.role not in {UserRole.ADMIN, UserRole.SUPERADMIN}:
        raise ValueError("Deal owner must be an ADMIN or SUPERADMIN.")


def validate_account_and_contact(
    account_repository: AccountRepository,
    contact_repository: ContactRepository,
    account_id: UUID | None,
    contact_id: UUID | None,
) -> None:
    if account_id is None and contact_id is None:
        raise ValueError("A deal requires an account or a contact.")

    account = None
    if account_id is not None:
        account = account_repository.get_by_id(account_id)

        if account is None or account.is_deleted:
            raise ValueError("Selected account not found.")

    if contact_id is not None:
        contact = contact_repository.get_by_id(contact_id)

        if contact is None or contact.is_deleted:
            raise ValueError("Selected contact not found.")

        if (
            account_id is not None
            and contact.account_id is not None
            and contact.account_id != account_id
        ):
            raise ValueError(
                "Selected contact does not belong to the selected account."
            )
