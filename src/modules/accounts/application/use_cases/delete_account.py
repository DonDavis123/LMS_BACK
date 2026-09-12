from datetime import datetime, timezone
from uuid import UUID

from src.modules.accounts.application.dto.delete_account import DeleteAccountDTO
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)


class DeleteAccountUseCase:

    def __init__(
        self,
        account_repository: AccountRepository,
        contact_repository: ContactRepository,
        transaction_manager: TransactionManager,
    ):
        self.account_repository = account_repository
        self.contact_repository = contact_repository
        self.transaction_manager = transaction_manager

    def execute(
        self,
        data: DeleteAccountDTO,
        current_user_id: UUID,
    ) -> None:

        account = self.account_repository.get_by_id(
            data.account_id,
        )

        if account is None:
            raise ValueError("Account not found.")

        if account.is_deleted:
            raise ValueError("Account is already deleted.")

        def deletion():

            # --------------------------------------------------
            # 1. Unlink Contacts
            # --------------------------------------------------

            self.contact_repository.unlink_account_contacts(
                account.id,
            )

            # --------------------------------------------------
            # 2. Soft-delete Account
            # --------------------------------------------------

            account.is_deleted = True

            # --------------------------------------------------
            # 3. Update audit information
            # --------------------------------------------------

            account.modified_by_id = current_user_id
            account.updated_at = datetime.now(timezone.utc)

            # --------------------------------------------------
            # 4. Persist Account
            # --------------------------------------------------

            self.account_repository.save(account)

        self.transaction_manager.execute(
            deletion,
        )