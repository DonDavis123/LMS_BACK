from uuid import UUID

from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.application.interfaces.session_revoker import SessionRevoker
from src.modules.users.application.interfaces.user_audit_log_repository import (
    UserAuditLogRepository,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User
from src.modules.users.domain.entities.user_audit_action import UserAuditAction
from src.modules.users.domain.entities.user_audit_log import UserAuditLog


class BlockUserUseCase:

    def __init__(
        self,
        user_repository: UserRepository,
        audit_log_repository: UserAuditLogRepository,
        session_revoker: SessionRevoker,
        transaction_manager: TransactionManager,
    ):
        self.user_repository = user_repository
        self.audit_log_repository = audit_log_repository
        self.session_revoker = session_revoker
        self.transaction_manager = transaction_manager

    def execute(
        self,
        current_user: User,
        user_id: UUID,
    ) -> User:
        self._require_superadmin(current_user)

        if current_user.id == user_id:
            raise ValueError("A superadmin cannot block their own account.")

        target_user = self.user_repository.get_by_id(user_id)
        if target_user is None:
            raise ValueError("User not found.")

        if target_user.is_deleted:
            raise ValueError("A deleted user cannot be blocked.")

        def change_status() -> User:
            updated_user = self.user_repository.set_active(
                user_id=user_id,
                is_active=False,
            )
            if updated_user is None:
                raise ValueError("User not found.")

            self.audit_log_repository.add(
                UserAuditLog.create(
                    action=UserAuditAction.USER_BLOCKED,
                    actor=current_user,
                    target=updated_user,
                )
            )
            # Blocking must also end sessions that could be revived on unblock.
            self.session_revoker.revoke_all_sessions(user_id)

            return updated_user

        return self.transaction_manager.execute(change_status)

    @staticmethod
    def _require_superadmin(current_user: User) -> None:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")
        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")
