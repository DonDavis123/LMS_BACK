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
    def get_all(self) -> list[Account]:
        pass