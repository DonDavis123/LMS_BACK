from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.accounts.application.dto.account_document import (
    GetAccountDocumentDTO,
)
from src.modules.accounts.domain.entities.account_document import AccountDocument


class AccountDocumentRepository(ABC):

    @abstractmethod
    def save(self, document: AccountDocument) -> AccountDocument:
        pass

    @abstractmethod
    def get_by_id(
        self,
        document_id: UUID,
        account_id: UUID,
    ) -> AccountDocument | None:
        """The document, only when it belongs to ``account_id``."""
        pass

    @abstractmethod
    def get_with_relations(
        self,
        document_id: UUID,
    ) -> GetAccountDocumentDTO | None:
        pass

    @abstractmethod
    def list_by_account_id(self, account_id: UUID) -> list[GetAccountDocumentDTO]:
        """Documents of one account, oldest first (the order they were added)."""
        pass

    @abstractmethod
    def delete(self, document_id: UUID) -> None:
        """Permanently remove the document row."""
        pass
