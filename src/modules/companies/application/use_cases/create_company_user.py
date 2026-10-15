import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from src.modules.companies.application.interfaces.company_repository import (
    CompanyRepository,
)
from src.modules.companies.application.interfaces.platform_audit_log_repository import (
    PlatformAuditLogRepository,
)
from src.modules.companies.application.use_cases._guards import require_platform_admin
from src.modules.companies.domain.entities.platform_audit_action import (
    PlatformAuditAction,
)
from src.modules.companies.domain.entities.platform_audit_log import PlatformAuditLog
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import MANAGEABLE_ROLES, UserRole
from src.modules.users.domain.entities.user import User


class CreateCompanyUserUseCase:

    def __init__(
        self,
        company_repository: CompanyRepository,
        user_repository_factory: Callable[[UUID], UserRepository],
        platform_audit_log_repository: PlatformAuditLogRepository,
        transaction_manager: TransactionManager,
    ):
        self.company_repository = company_repository
        self.user_repository_factory = user_repository_factory
        self.platform_audit_log_repository = platform_audit_log_repository
        self.transaction_manager = transaction_manager

    def execute(
        self,
        current_user: User,
        company_id: UUID,
        name: str,
        email: str,
        password: str,
        role: UserRole,
    ) -> User:
        require_platform_admin(current_user)

        if self.company_repository.get_by_id(company_id) is None:
            raise ValueError("Company not found.")

        if role not in MANAGEABLE_ROLES:
            raise ValueError(f"{role.value} users cannot be created.")

        name = name.strip()
        email = email.strip().lower()
        if not name:
            raise ValueError("Name is required.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        # Emails are unique platform-wide; the scoped user repository only
        # sees this company.
        if self.company_repository.email_exists(email):
            raise ValueError("User with this email already exists.")

        now = datetime.now(timezone.utc)
        user = User(
            id=uuid.uuid4(),
            name=name,
            email=email,
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
            company_id=company_id,
        )

        def create() -> User:
            created = self.user_repository_factory(company_id).create(
                user=user,
                password=password,
            )
            self.platform_audit_log_repository.add(
                PlatformAuditLog.create(
                    action=PlatformAuditAction.COMPANY_USER_CREATED,
                    actor=current_user,
                    company_id=company_id,
                    target=created,
                    metadata={"role": created.role.value},
                )
            )
            return created

        return self.transaction_manager.execute(create)
