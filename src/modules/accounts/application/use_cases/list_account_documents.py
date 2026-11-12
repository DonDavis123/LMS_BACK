from uuid import UUID

from src.modules.accounts.application.dto.account_document import (
    GetAccountDocumentDTO,
)
from src.modules.accounts.application.interfaces.account_document_repository import (
    AccountDocumentRepository,
)
from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)


class ListAccountDocumentsUseCase:

    def __init__(
        self,
        account_repository: AccountRepository,
        document_repository: AccountDocumentRepository,
    ):
        self.account_repository = account_repository
        self.document_repository = document_repository

    def execute(self, account_id: UUID) -> list[GetAccountDocumentDTO]:
        account = self.account_repository.get_by_id(account_id)

        if account is None or account.is_deleted:
            raise ValueError("Account not found.")

        return self.document_repository.list_by_account_id(account.id)
