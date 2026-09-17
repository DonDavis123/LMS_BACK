from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.accounts.domain.entities.account import Account


class AccountRepository(ABC):

    @abstractmethod
    def save(self, account: Account) -> Account:
        pass

    @abstractmethod
    def get_by_id(self, account_id: UUID) -> Account | None:
        pass

    @abstractmethod
    def get_by_id_with_owner(
        self,
        account_id: UUID,
    ) -> tuple[Account, str | None] | None:
        pass

    @abstractmethod
    def get_all(self) -> list[Account]:
        pass

    @abstractmethod
    def get_all_with_owner(
        self,
    ) -> list[tuple[Account, str | None]]:
        pass

    @abstractmethod
    def find_conversion_matches(
        self,
        account_name: str,
        website: str | None,
        phone: str | None,
    ) -> list[Account]:
        pass

