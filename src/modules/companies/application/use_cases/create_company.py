import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from src.modules.companies.application.dto.company_dto import CreateCompanyDTO
from src.modules.companies.application.interfaces.company_repository import (
    CompanyRepository,
)
from src.modules.companies.application.interfaces.platform_audit_log_repository import (
    PlatformAuditLogRepository,
)
from src.modules.companies.domain.entities.platform_audit_action import (
    PlatformAuditAction,
)
from src.modules.companies.domain.entities.platform_audit_log import PlatformAuditLog
from src.modules.companies.application.use_cases._guards import require_platform_admin
from src.modules.companies.domain.entities.company import Company
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.application.interfaces.user_audit_log_repository import (
    UserAuditLogRepository,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User
from src.modules.users.domain.entities.user_audit_action import UserAuditAction
from src.modules.users.domain.entities.user_audit_log import UserAuditLog


class CreateCompanyUseCase:
    """Creates a company and its first company SUPERADMIN atomically."""

    def __init__(
        self,
        company_repository: CompanyRepository,
        user_repository_factory: Callable[[UUID], UserRepository],
        audit_log_repository_factory: Callable[[UUID], UserAuditLogRepository],
        transaction_manager: TransactionManager,
        platform_audit_log_repository: PlatformAuditLogRepository,
    ):
        self.company_repository = company_repository
        self.platform_audit_log_repository = platform_audit_log_repository
        self.user_repository_factory = user_repository_factory
        self.audit_log_repository_factory = audit_log_repository_factory
        self.transaction_manager = transaction_manager

    def execute(
        self,
        current_user: User,
        data: CreateCompanyDTO,
    ) -> tuple[Company, User]:
        require_platform_admin(current_user)

        company_name = data.company_name.strip()
        admin_name = data.admin_name.strip()
        admin_email = data.admin_email.strip().lower()
        website = (data.website or "").strip() or None

        if not company_name:
            raise ValueError("Company name is required.")
        if not admin_name:
            raise ValueError("Admin name is required.")
        if len(data.admin_password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        # The user repository is company-scoped, so its own duplicate check
        # cannot see other companies. Emails are unique platform-wide.
        if self.company_repository.email_exists(admin_email):
            raise ValueError("User with this email already exists.")

        def create() -> tuple[Company, User]:
            company = self.company_repository.create(
                name=company_name,
                website=website,
                created_by_id=current_user.id,
            )

            now = datetime.now(timezone.utc)
            admin = self.user_repository_factory(company.id).create(
                user=User(
                    id=uuid.uuid4(),
                    name=admin_name,
                    email=admin_email,
                    role=UserRole.SUPERADMIN,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                    company_id=company.id,
                ),
                password=data.admin_password,
            )

            self.audit_log_repository_factory(company.id).add(
                UserAuditLog.create(
                    action=UserAuditAction.USER_CREATED,
                    actor=current_user,
                    target=admin,
                    metadata={
                        "role": admin.role.value,
                        "created_with_company": True,
                    },
                )
            )
            self.platform_audit_log_repository.add(
                PlatformAuditLog.create(
                    action=PlatformAuditAction.COMPANY_CREATED,
                    actor=current_user,
                    company_id=company.id,
                    target=admin,
                    metadata={"name": company.name, "slug": company.slug},
                )
            )
            return company, admin

        return self.transaction_manager.execute(create)
