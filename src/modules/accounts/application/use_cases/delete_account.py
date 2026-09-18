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
from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)
from src.modules.timeline.application.interfaces.timeline_repository import (
    TimelineRepository,
)


class DeleteAccountUseCase:

    def __init__(
        self,
        account_repository: AccountRepository,
        contact_repository: ContactRepository,
        task_repository: TaskRepository,
        timeline_repository: TimelineRepository,
        transaction_manager: TransactionManager,
    ):
        self.account_repository = account_repository
        self.contact_repository = contact_repository
        self.task_repository = task_repository
        self.timeline_repository = timeline_repository
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

            # --------------------------------------------------
            # 5. Handle Tasks associated with the Account
            # --------------------------------------------------

            # The current Task rules require an Account to be paired with a
            # Contact. Such a Task remains a Contact task after Account deletion,
            # so remove only the optional Account relationship. Any legacy/invalid
            # Account-only task is still soft-deleted by the repository.
            self.task_repository.soft_delete_by_account_id(
                account.id,
            )
            self.task_repository.unlink_account_from_contact_tasks(
                account.id,
            )

            # --------------------------------------------------
            # 6. Soft-delete Timeline events for the Account
            # --------------------------------------------------

            self.timeline_repository.soft_delete_by_entity(
                "ACCOUNT",
                account.id,
            )

        self.transaction_manager.execute(
            deletion,
        )
