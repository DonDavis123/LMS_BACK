import uuid

from datetime import datetime, timezone

from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.application.interfaces.user_audit_log_repository import (
    UserAuditLogRepository,
)
from src.modules.users.application.interfaces.user_repository import (
    UserRepository,
)
from src.modules.users.domain.entities.role import MANAGEABLE_ROLES, UserRole
from src.modules.users.domain.entities.user import User
from src.modules.users.domain.entities.user_audit_action import UserAuditAction
from src.modules.users.domain.entities.user_audit_log import UserAuditLog


class CreateUserUseCase:

    def __init__(
        self,
        user_repository: UserRepository,
        audit_log_repository: UserAuditLogRepository,
        transaction_manager: TransactionManager,
    ):
        self.user_repository = user_repository
        self.audit_log_repository = audit_log_repository
        self.transaction_manager = transaction_manager

    def execute(
        self,
        current_user: User,
        name: str,
        email: str,
        password: str,
        role: UserRole,
    ) -> User:

        if not current_user.is_active:
            raise ValueError(
                "Inactive users cannot create users."
            )

        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError(
                "Only superadmins can create users."
            )

        if role not in MANAGEABLE_ROLES:
            raise ValueError(
                f"{role.value} users cannot be created."
            )

        existing_user = self.user_repository.get_by_email(email.strip().lower())

        if existing_user:
            raise ValueError(
                "User with this email already exists."
            )

        now = datetime.now(timezone.utc)

        user = User(
            id=uuid.uuid4(),
            name=name.strip(),
            email=email.strip().lower(),
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        def create() -> User:
            created_user = self.user_repository.create(
                user=user,
                password=password,
            )
            self.audit_log_repository.add(
                UserAuditLog.create(
                    action=UserAuditAction.USER_CREATED,
                    actor=current_user,
                    target=created_user,
                    metadata={"role": created_user.role.value},
                )
            )
            return created_user

        return self.transaction_manager.execute(create)
