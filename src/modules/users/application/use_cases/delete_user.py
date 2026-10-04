from datetime import datetime, timezone
from uuid import UUID

from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)
from src.modules.meetings.application.interfaces.meeting_repository import (
    MeetingRepository,
)
from src.modules.notifications.application.interfaces.notification_repository import (
    NotificationRepository,
)
from src.modules.reminders.application.interfaces.reminder_repository import (
    ReminderRepository,
)
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
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


class DeleteUserUseCase:
    """Retire (soft-delete) a user.

    Leads, Contacts, Accounts and Meeting hosting are transferred to an
    explicitly chosen replacement user (optional only when none of them
    exist). Tasks, Reminders and Notifications
    belonging to the retired user are permanently deleted. Timeline is
    untouched. The User row is kept and marked as deleted/inactive.
    The whole workflow runs in one transaction.
    """

    REPLACEMENT_ROLES = {UserRole.ADMIN, UserRole.SUPERADMIN}

    def __init__(
        self,
        user_repository: UserRepository,
        lead_repository: LeadRepository,
        contact_repository: ContactRepository,
        account_repository: AccountRepository,
        meeting_repository: MeetingRepository,
        task_repository: TaskRepository,
        reminder_repository: ReminderRepository,
        notification_repository: NotificationRepository,
        audit_log_repository: UserAuditLogRepository,
        session_revoker: SessionRevoker,
        transaction_manager: TransactionManager,
    ):
        self.user_repository = user_repository
        self.lead_repository = lead_repository
        self.contact_repository = contact_repository
        self.account_repository = account_repository
        self.meeting_repository = meeting_repository
        self.task_repository = task_repository
        self.reminder_repository = reminder_repository
        self.notification_repository = notification_repository
        self.audit_log_repository = audit_log_repository
        self.session_revoker = session_revoker
        self.transaction_manager = transaction_manager

    def execute(
        self,
        current_user: User,
        user_id: UUID,
        replacement_user_id: UUID | None = None,
    ) -> None:
        self._require_superadmin(current_user)

        if current_user.id == user_id:
            raise ValueError("A superadmin cannot delete their own account.")

        target_user = self.user_repository.get_by_id(user_id)
        if target_user is None:
            raise ValueError("User not found.")
        if target_user.is_deleted:
            raise ValueError("User has already been deleted.")

        # A replacement that is supplied is always fully validated, even
        # when there turns out to be nothing to transfer.
        replacement_user = (
            self._validate_replacement_user(
                target_user=target_user,
                replacement_user_id=replacement_user_id,
            )
            if replacement_user_id is not None
            else None
        )

        def retirement() -> None:
            # Decided inside the transaction, right before the changes, so
            # the answer cannot go stale between a check and the retirement.
            if self._has_records_to_transfer(target_user.id):
                if replacement_user is None:
                    raise ValueError("Replacement user is required.")

                # Ownership transfers (records are kept).
                self.lead_repository.transfer_ownership(
                    from_user_id=target_user.id,
                    to_user_id=replacement_user.id,
                )
                self.contact_repository.transfer_ownership(
                    from_user_id=target_user.id,
                    to_user_id=replacement_user.id,
                )
                self.account_repository.transfer_ownership(
                    from_user_id=target_user.id,
                    to_user_id=replacement_user.id,
                )
                self.meeting_repository.transfer_host(
                    from_user_id=target_user.id,
                    to_user_id=replacement_user.id,
                )

            # Permanent cleanup. Tasks first so their dependent
            # reminders/notifications are removed before the user-scoped ones.
            self.task_repository.delete_by_owner_id(target_user.id)
            self.reminder_repository.delete_by_user_id(target_user.id)
            self.notification_repository.delete_by_user_id(target_user.id)

            # Timeline is intentionally preserved.

            if self.user_repository.soft_delete(
                user_id=target_user.id,
                deleted_at=datetime.now(timezone.utc),
            ) is None:
                raise ValueError("User not found.")

            self.audit_log_repository.add(
                UserAuditLog.create(
                    action=UserAuditAction.USER_RETIRED,
                    actor=current_user,
                    target=target_user,
                    metadata=(
                        {
                            "replacement_user_id": str(replacement_user.id),
                            "replacement_user_email": replacement_user.email,
                        }
                        if replacement_user is not None
                        else {}
                    ),
                )
            )
            self.session_revoker.revoke_all_sessions(target_user.id)

        self.transaction_manager.execute(retirement)

    def _has_records_to_transfer(self, user_id: UUID) -> bool:
        return (
            self.lead_repository.count_by_owner_id(user_id) > 0
            or self.contact_repository.count_by_owner_id(user_id) > 0
            or self.account_repository.count_by_owner_id(user_id) > 0
            or self.meeting_repository.count_by_host_id(user_id) > 0
        )

    def _validate_replacement_user(
        self,
        target_user: User,
        replacement_user_id: UUID,
    ) -> User:
        if replacement_user_id == target_user.id:
            raise ValueError(
                "Replacement user must be different from the user being deleted."
            )

        replacement_user = self.user_repository.get_by_id(replacement_user_id)
        if replacement_user is None:
            raise ValueError("Replacement user not found.")
        if replacement_user.is_deleted:
            raise ValueError("Replacement user has been deleted.")
        if not replacement_user.is_active:
            raise ValueError("Replacement user must be active.")
        if replacement_user.role not in self.REPLACEMENT_ROLES:
            raise ValueError(
                "Replacement user must be an Admin or Superadmin."
            )

        return replacement_user

    @staticmethod
    def _require_superadmin(current_user: User) -> None:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")
        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")
