from datetime import datetime, timezone

from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.application.dto.update_user import UpdateUserDTO
from src.modules.users.application.interfaces.session_revoker import SessionRevoker
from src.modules.users.application.interfaces.user_audit_log_repository import (
    UserAuditLogRepository,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import MANAGEABLE_ROLES, UserRole
from src.modules.users.domain.entities.user import User
from src.modules.users.domain.entities.user_audit_action import UserAuditAction
from src.modules.users.domain.entities.user_audit_log import UserAuditLog


class UpdateUserUseCase:

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
        data: UpdateUserDTO,
    ) -> User:
        self._require_superadmin(current_user)

        target_user = self.user_repository.get_by_id(data.user_id)
        if target_user is None:
            raise ValueError("User not found.")

        if target_user.is_deleted:
            raise ValueError("A deleted user cannot be updated.")

        if (
            data.role is not None
            and target_user.id == current_user.id
            and data.role != target_user.role
        ):
            # Prevents the last remaining superadmin from locking
            # everyone out of user management.
            raise ValueError("A superadmin cannot change their own role.")

        previous_role = target_user.role
        changed_fields: dict[str, dict[str, str]] = {}

        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise ValueError("Name cannot be empty.")
            if name != target_user.name:
                changed_fields["name"] = {"from": target_user.name, "to": name}
            target_user.name = name

        if data.email is not None:
            email = data.email.strip().lower()
            if not email:
                raise ValueError("Email cannot be empty.")

            existing_user = self.user_repository.get_by_email(email)
            if existing_user is not None and existing_user.id != target_user.id:
                raise ValueError("User with this email already exists.")

            if email != target_user.email:
                changed_fields["email"] = {"from": target_user.email, "to": email}
            target_user.email = email

        role_changed = False
        if data.role is not None:
            if not isinstance(data.role, UserRole):
                raise ValueError("Invalid user role.")
            if data.role not in MANAGEABLE_ROLES and data.role != previous_role:
                raise ValueError(f"Users cannot be assigned the {data.role.value} role.")
            role_changed = data.role != previous_role
            target_user.role = data.role

        target_user.updated_at = datetime.now(timezone.utc)

        def update() -> User:
            updated_user = self.user_repository.update(target_user)

            if changed_fields:
                self.audit_log_repository.add(
                    UserAuditLog.create(
                        action=UserAuditAction.USER_UPDATED,
                        actor=current_user,
                        target=updated_user,
                        metadata={"changes": changed_fields},
                    )
                )

            if role_changed:
                self.audit_log_repository.add(
                    UserAuditLog.create(
                        action=UserAuditAction.USER_ROLE_CHANGED,
                        actor=current_user,
                        target=updated_user,
                        metadata={
                            "from": previous_role.value,
                            "to": updated_user.role.value,
                        },
                    )
                )
                # Force a fresh login so the session reflects the new role.
                self.session_revoker.revoke_all_sessions(updated_user.id)

            return updated_user

        return self.transaction_manager.execute(update)

    @staticmethod
    def _require_superadmin(current_user: User) -> None:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")

        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")
