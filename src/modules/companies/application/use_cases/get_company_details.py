from uuid import UUID

from src.modules.companies.application.dto.company_dto import CompanyDetailDTO
from src.modules.companies.application.interfaces.company_repository import (
    CompanyRepository,
)
from src.modules.companies.application.use_cases._guards import require_platform_admin
from src.modules.users.domain.entities.user import User


class GetCompanyDetailsUseCase:

    def __init__(self, company_repository: CompanyRepository):
        self.company_repository = company_repository

    def execute(self, current_user: User, company_id: UUID) -> CompanyDetailDTO:
        require_platform_admin(current_user)

        detail = self.company_repository.get_detail(company_id)
        if detail is None:
            raise ValueError("Company not found.")
        return detail
