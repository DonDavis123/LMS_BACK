from uuid import UUID

from src.modules.companies.application.interfaces.company_repository import (
    CompanyRepository,
)
from src.modules.companies.application.use_cases._guards import require_platform_admin
from src.modules.companies.domain.entities.company import Company
from src.modules.companies.domain.entities.company_status import CompanyStatus
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.domain.entities.user import User


class ActivateCompanyUseCase:

    def __init__(
        self,
        company_repository: CompanyRepository,
        transaction_manager: TransactionManager,
    ):
        self.company_repository = company_repository
        self.transaction_manager = transaction_manager

    def execute(self, current_user: User, company_id: UUID) -> Company:
        require_platform_admin(current_user)

        company = self.company_repository.get_by_id(company_id)
        if company is None:
            raise ValueError("Company not found.")
        if company.status is CompanyStatus.ACTIVE:
            raise ValueError("Company is already active.")

        return self.transaction_manager.execute(
            lambda: self.company_repository.set_status(
                company_id=company_id,
                status=CompanyStatus.ACTIVE,
                reason="",
                changed_by_id=current_user.id,
            )
        )
