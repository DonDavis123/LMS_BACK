from uuid import UUID

from src.modules.accounts.application.dto.account_summary import AccountSummaryResponseDTO
from src.modules.accounts.application.interfaces.account_repository import AccountRepository
from src.modules.accounts.application.interfaces.account_summary_repository import (
    AccountSummaryRepository,
)


class GetAccountSummaryUseCase:
    """Reads the stored summary of an account. Never calls the model."""

    def __init__(
        self,
        account_repository: AccountRepository,
        summary_repository: AccountSummaryRepository,
    ):
        self.account_repository = account_repository
        self.summary_repository = summary_repository

    def execute(self, account_id: UUID) -> AccountSummaryResponseDTO | None:
        """The stored summary, or ``None`` when none was generated yet."""
        account = self.account_repository.get_by_id(account_id)

        if account is None or account.is_deleted:
            raise ValueError("Company not found.")

        summary = self.summary_repository.get_by_account_id(account.id)

        if summary is None:
            return None

        return AccountSummaryResponseDTO.from_entity(summary)
