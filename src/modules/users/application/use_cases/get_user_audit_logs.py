from uuid import UUID

from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.application.interfaces.user_audit_log_repository import (
    UserAuditLogRepository,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User
from src.modules.users.domain.entities.user_audit_action import UserAuditAction
from src.modules.users.domain.entities.user_audit_log import UserAuditLog


class GetUserAuditLogsUseCase:

    def __init__(
        self,
        audit_log_repository: UserAuditLogRepository,
        user_repository: UserRepository,
    ):
        self.audit_log_repository = audit_log_repository
        self.user_repository = user_repository

    def execute(
        self,
        current_user: User,
        query: ListQuery,
        target_user_id: UUID | None = None,
        action: UserAuditAction | None = None,
    ) -> PaginatedResult[UserAuditLog]:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")
        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")

        # A user of another company behaves exactly like a missing one.
        if (
            target_user_id is not None
            and self.user_repository.get_by_id(target_user_id) is None
        ):
            raise ValueError("User not found.")

        return self.audit_log_repository.get_all(
            query=query,
            target_user_id=target_user_id,
            action=action,
        )
