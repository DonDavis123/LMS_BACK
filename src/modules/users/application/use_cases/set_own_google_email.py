from datetime import datetime, timezone
from uuid import UUID

from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.application.interfaces.user_audit_log_repository import (
    UserAuditLogRepository,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.application.services.google_email import (
    normalize_google_email,
)
from src.modules.users.domain.entities.user import User
from src.modules.users.domain.entities.user_audit_action import UserAuditAction
from src.modules.users.domain.entities.user_audit_log import UserAuditLog


class SetOwnGoogleEmailUseCase:

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
        user_id: UUID,
        google_email: str | None,
    ) -> User:
        # Always the caller's own record: the id comes from request.user.
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found.")

        if user.is_deleted or not user.is_active:
            raise ValueError("Inactive users cannot update their profile.")

        normalized = normalize_google_email(google_email)
        if normalized == user.google_email:
            return user

        previous = user.google_email
        user.google_email = normalized
        user.updated_at = datetime.now(timezone.utc)

        def update() -> User:
            updated_user = self.user_repository.update(user)
            self.audit_log_repository.add(
                UserAuditLog.create(
                    action=UserAuditAction.USER_UPDATED,
                    actor=updated_user,
                    target=updated_user,
                    metadata={
                        "changes": {
                            "google_email": {
                                "from": previous,
                                "to": normalized,
                            },
                        },
                    },
                )
            )
            return updated_user

        return self.transaction_manager.execute(update)
