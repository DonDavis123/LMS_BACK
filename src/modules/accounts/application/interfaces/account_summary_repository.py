from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.accounts.domain.entities.account_summary import AccountSummary


class AccountSummaryRepository(ABC):
    """Storage of the one current summary of each account."""

    @abstractmethod
    def get_by_account_id(self, account_id: UUID) -> AccountSummary | None:
        pass

    @abstractmethod
    def replace_for_account(self, summary: AccountSummary) -> AccountSummary:
        """Permanently delete the account's previous summary (if any) and store
        ``summary`` in its place, in one transaction.

        Nothing of the old summary is kept: no history, no soft delete.
        """
        pass

    @abstractmethod
    def delete_by_account_id(self, account_id: UUID) -> int:
        """Permanently delete the account's summary. Returns how many were removed."""
        pass
