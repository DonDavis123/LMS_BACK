from abc import ABC, abstractmethod


class PicklistUsageGateway(ABC):
    """Finds and rewrites the records that store an option's text."""

    @abstractmethod
    def count_by_value(self, module: str, field: str) -> dict[str, int]:
        """How many records use each value of the field."""

    @abstractmethod
    def count(self, module: str, field: str, value: str) -> int:
        ...

    @abstractmethod
    def replace_value(
        self, module: str, field: str, old_value: str, new_value: str
    ) -> int:
        """Point every record using ``old_value`` at ``new_value``. Returns rows changed."""
