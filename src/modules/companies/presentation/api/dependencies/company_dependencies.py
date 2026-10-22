from src.modules.companies.application.use_cases.activate_company import (
    ActivateCompanyUseCase,
)
from src.modules.companies.application.use_cases.block_company_user import (
    ChangeCompanyUserStatusUseCase,
)
from src.modules.companies.application.use_cases.create_company_user import (
    CreateCompanyUserUseCase,
)
from src.modules.companies.application.use_cases.get_company_users import (
    GetCompanyUsersUseCase,
)
from src.modules.companies.application.use_cases.get_platform_audit_logs import (
    GetPlatformAuditLogsUseCase,
)
from src.modules.companies.application.use_cases.get_platform_overview import (
    GetPlatformOverviewUseCase,
)
from src.modules.companies.application.use_cases.reset_company_user_password import (
    ResetCompanyUserPasswordUseCase,
)
from src.modules.companies.infrastructure.persistence.django_platform_audit_log_repository import (
    DjangoPlatformAuditLogRepository,
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
from src.modules.lead_capture.infrastructure.persistence.django_lead_form_repository import (
    DjangoLeadFormRepository,
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


def get_platform_audit_log_repository() -> DjangoPlatformAuditLogRepository:
    return DjangoPlatformAuditLogRepository()


def _user_repository_factory(company_id):
    return DjangoUserRepository(company_id=company_id)


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
        platform_audit_log_repository=get_platform_audit_log_repository(),
        lead_form_repository_factory=lambda company_id: DjangoLeadFormRepository(
            company_id=company_id
        ),
    )


def get_update_company_use_case() -> UpdateCompanyUseCase:
    return UpdateCompanyUseCase(
        company_repository=get_company_repository(),
        platform_audit_log_repository=get_platform_audit_log_repository(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_suspend_company_use_case() -> SuspendCompanyUseCase:
    return SuspendCompanyUseCase(
        company_repository=get_company_repository(),
        session_revoker=JWTSessionRevoker(),
        transaction_manager=DjangoTransactionManager(),
        platform_audit_log_repository=get_platform_audit_log_repository(),
    )


def get_activate_company_use_case() -> ActivateCompanyUseCase:
    return ActivateCompanyUseCase(
        company_repository=get_company_repository(),
        transaction_manager=DjangoTransactionManager(),
        platform_audit_log_repository=get_platform_audit_log_repository(),
    )


def get_company_users_use_case() -> GetCompanyUsersUseCase:
    return GetCompanyUsersUseCase(
        company_repository=get_company_repository(),
        user_repository_factory=_user_repository_factory,
    )


def get_create_company_user_use_case() -> CreateCompanyUserUseCase:
    return CreateCompanyUserUseCase(
        company_repository=get_company_repository(),
        user_repository_factory=_user_repository_factory,
        platform_audit_log_repository=get_platform_audit_log_repository(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_reset_company_user_password_use_case() -> ResetCompanyUserPasswordUseCase:
    return ResetCompanyUserPasswordUseCase(
        company_repository=get_company_repository(),
        user_repository_factory=_user_repository_factory,
        platform_audit_log_repository=get_platform_audit_log_repository(),
        session_revoker=JWTSessionRevoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def _status_use_case(block: bool) -> ChangeCompanyUserStatusUseCase:
    return ChangeCompanyUserStatusUseCase(
        company_repository=get_company_repository(),
        user_repository_factory=_user_repository_factory,
        platform_audit_log_repository=get_platform_audit_log_repository(),
        session_revoker=JWTSessionRevoker(),
        transaction_manager=DjangoTransactionManager(),
        block=block,
    )


def get_block_company_user_use_case() -> ChangeCompanyUserStatusUseCase:
    return _status_use_case(block=True)


def get_unblock_company_user_use_case() -> ChangeCompanyUserStatusUseCase:
    return _status_use_case(block=False)


def get_platform_overview_use_case() -> GetPlatformOverviewUseCase:
    return GetPlatformOverviewUseCase(company_repository=get_company_repository())


def get_platform_audit_logs_use_case() -> GetPlatformAuditLogsUseCase:
    return GetPlatformAuditLogsUseCase(
        audit_log_repository=get_platform_audit_log_repository()
    )
