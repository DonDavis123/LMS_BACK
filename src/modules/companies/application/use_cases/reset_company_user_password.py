from collections.abc import Callable
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
from src.modules.users.application.interfaces.session_revoker import SessionRevoker
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.user import User


class ResetCompanyUserPasswordUseCase:

    def __init__(
        self,
        company_repository: CompanyRepository,
        user_repository_factory: Callable[[UUID], UserRepository],
        platform_audit_log_repository: PlatformAuditLogRepository,
        session_revoker: SessionRevoker,
        transaction_manager: TransactionManager,
    ):
        self.company_repository = company_repository
        self.user_repository_factory = user_repository_factory
        self.platform_audit_log_repository = platform_audit_log_repository
        self.session_revoker = session_revoker
        self.transaction_manager = transaction_manager

    def execute(
        self,
        current_user: User,
        company_id: UUID,
        user_id: UUID,
        new_password: str,
    ) -> None:
        require_platform_admin(current_user)

        if self.company_repository.get_by_id(company_id) is None:
            raise ValueError("Company not found.")

        user_repository = self.user_repository_factory(company_id)
        target = user_repository.get_by_id(user_id)
        if target is None:
            raise ValueError("User not found.")
        if target.is_deleted:
            raise ValueError("A deleted user's password cannot be reset.")
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        def reset() -> None:
            if user_repository.set_password(
                user_id=user_id,
                password=new_password,
            ) is None:
                raise ValueError("User not found.")

            # The password itself is never written to the audit log.
            self.platform_audit_log_repository.add(
                PlatformAuditLog.create(
                    action=PlatformAuditAction.COMPANY_USER_PASSWORD_RESET,
                    actor=current_user,
                    company_id=company_id,
                    target=target,
                )
            )
            self.session_revoker.revoke_all_sessions(user_id)

        self.transaction_manager.execute(reset)
