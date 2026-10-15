from src.modules.companies.application.dto.company_dto import CompanyListDTO
from src.modules.companies.application.interfaces.company_repository import (
    CompanyRepository,
)
from src.modules.companies.application.use_cases._guards import require_platform_admin
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.domain.entities.user import User


class GetCompaniesUseCase:

    def __init__(self, company_repository: CompanyRepository):
        self.company_repository = company_repository

    def execute(
        self,
        current_user: User,
        query: ListQuery,
    ) -> PaginatedResult[CompanyListDTO]:
        require_platform_admin(current_user)
        return self.company_repository.get_all(query)
