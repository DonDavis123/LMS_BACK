from src.modules.companies.application.use_cases.activate_company import (
    ActivateCompanyUseCase,
)
from src.modules.companies.application.use_cases.create_company import (
    CreateCompanyUseCase,
)
from src.modules.companies.application.use_cases.get_companies import (
    GetCompaniesUseCase,
)
from src.modules.companies.application.use_cases.get_company_details import (
    GetCompanyDetailsUseCase,
)
from src.modules.companies.application.use_cases.suspend_company import (
    SuspendCompanyUseCase,
)
from src.modules.companies.application.use_cases.update_company import (
    UpdateCompanyUseCase,
)
from src.modules.companies.infrastructure.persistence.django_company_repository import (
    DjangoCompanyRepository,
)
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from src.modules.users.infrastructure.persistence.user_audit_log_repository import (
    DjangoUserAuditLogRepository,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)
from src.modules.users.infrastructure.security.jwt_session_revoker import (
    JWTSessionRevoker,
)


def get_company_repository() -> DjangoCompanyRepository:
    return DjangoCompanyRepository()


def get_companies_use_case() -> GetCompaniesUseCase:
    return GetCompaniesUseCase(company_repository=get_company_repository())


def get_company_details_use_case() -> GetCompanyDetailsUseCase:
    return GetCompanyDetailsUseCase(company_repository=get_company_repository())


def get_create_company_use_case() -> CreateCompanyUseCase:
    return CreateCompanyUseCase(
        company_repository=get_company_repository(),
        user_repository_factory=lambda company_id: DjangoUserRepository(
            company_id=company_id
        ),
        audit_log_repository_factory=lambda company_id: DjangoUserAuditLogRepository(
            company_id=company_id
        ),
        transaction_manager=DjangoTransactionManager(),
    )


def get_update_company_use_case() -> UpdateCompanyUseCase:
    return UpdateCompanyUseCase(company_repository=get_company_repository())


def get_suspend_company_use_case() -> SuspendCompanyUseCase:
    return SuspendCompanyUseCase(
        company_repository=get_company_repository(),
        session_revoker=JWTSessionRevoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_activate_company_use_case() -> ActivateCompanyUseCase:
    return ActivateCompanyUseCase(
        company_repository=get_company_repository(),
        transaction_manager=DjangoTransactionManager(),
    )
