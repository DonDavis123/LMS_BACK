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
from src.modules.users.application.interfaces.session_revoker import SessionRevoker
from src.modules.users.domain.entities.user import User


class SuspendCompanyUseCase:

    def __init__(
        self,
        company_repository: CompanyRepository,
        session_revoker: SessionRevoker,
        transaction_manager: TransactionManager,
    ):
        self.company_repository = company_repository
        self.session_revoker = session_revoker
        self.transaction_manager = transaction_manager

    def execute(
        self,
        current_user: User,
        company_id: UUID,
        reason: str,
    ) -> Company:
        require_platform_admin(current_user)

        reason = (reason or "").strip()
        if not reason:
            raise ValueError("Reason is required.")

        company = self.company_repository.get_by_id(company_id)
        if company is None:
            raise ValueError("Company not found.")
        if company.status is CompanyStatus.SUSPENDED:
            raise ValueError("Company is already suspended.")

        def suspend() -> Company:
            updated = self.company_repository.set_status(
                company_id=company_id,
                status=CompanyStatus.SUSPENDED,
                reason=reason,
                changed_by_id=current_user.id,
            )
            for user_id in self.company_repository.get_user_ids(company_id):
                self.session_revoker.revoke_all_sessions(user_id)
            return updated

        return self.transaction_manager.execute(suspend)
