from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.companies.application.dto.company_dto import (
    CompanyDetailDTO,
    CompanyListDTO,
)
from src.modules.companies.domain.entities.company import Company
from src.modules.companies.domain.entities.company_status import CompanyStatus
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class CompanyRepository(ABC):

    @abstractmethod
    def get_all(self, query: ListQuery) -> PaginatedResult[CompanyListDTO]:
        pass

    @abstractmethod
    def get_by_id(self, company_id: UUID) -> Company | None:
        pass

    @abstractmethod
    def get_detail(self, company_id: UUID) -> CompanyDetailDTO | None:
        pass

    @abstractmethod
    def create(
        self,
        name: str,
        website: str | None,
        created_by_id: UUID,
    ) -> Company:
        """Create an ACTIVE company with a unique, auto-generated slug."""
        pass

    @abstractmethod
    def update(
        self,
        company_id: UUID,
        name: str | None,
        website: str | None,
        update_website: bool,
    ) -> Company:
        pass

    @abstractmethod
    def set_status(
        self,
        company_id: UUID,
        status: CompanyStatus,
        reason: str,
        changed_by_id: UUID,
    ) -> Company:
        pass

    @abstractmethod
    def email_exists(self, email: str) -> bool:
        """Case-insensitive, across ALL companies."""
        pass

    @abstractmethod
    def get_user_ids(self, company_id: UUID) -> list[UUID]:
        pass
