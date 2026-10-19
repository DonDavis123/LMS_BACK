from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.picklists.domain.entities.picklist_option import PicklistOption


class PicklistRepository(ABC):
    """Options of ONE company (the implementation is scoped to it)."""

    @abstractmethod
    def ensure_defaults(self, module: str) -> None:
        """Seed the built-in options for every field of ``module`` that has none yet."""

    @abstractmethod
    def list_options(
        self, module: str, field: str, include_inactive: bool = False
    ) -> list[PicklistOption]:
        ...

    @abstractmethod
    def get_by_id(self, option_id: UUID) -> PicklistOption | None:
        ...

    @abstractmethod
    def find_by_value(
        self, module: str, field: str, value: str
    ) -> PicklistOption | None:
        """Case-insensitive lookup."""

    @abstractmethod
    def count(self, module: str, field: str) -> int:
        ...

    @abstractmethod
    def next_sort_order(self, module: str, field: str) -> int:
        ...

    @abstractmethod
    def save(self, option: PicklistOption) -> PicklistOption:
        ...

    @abstractmethod
    def save_order(self, options: list[PicklistOption]) -> None:
        ...

    @abstractmethod
    def delete(self, option_id: UUID) -> None:
        ...
