from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PublicFormTarget:
    """What a public link resolves to: the company and how to show it."""

    company_id: UUID
    company_name: str


class PublicLeadFormLookup(ABC):
    @abstractmethod
    def find_by_token(self, public_token: str) -> PublicFormTarget | None:
        """The company behind a public link token, or ``None`` if unknown.

        This is the only place tenant scoping is bypassed: a visitor has no
        login, so the company can only come from the token. Everything after
        it must use repositories pinned to ``PublicFormTarget.company_id``.
        """
