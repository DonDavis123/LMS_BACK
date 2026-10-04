from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)
from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import (
    DjangoMeetingRepository,
)
from src.modules.notifications.infrastructure.persistence.django_notification_repository import (
    DjangoNotificationRepository,
)
from src.modules.reminders.infrastructure.persistence.django_reminder_repository import (
    DjangoReminderRepository,
)
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from src.modules.tasks.infrastructure.persistence.django_task_repository import (
    DjangoTaskRepository,
)
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import (
    DjangoTimelineRepository,
)
from src.modules.users.application.use_cases.block_user import BlockUserUseCase
from src.modules.users.application.use_cases.create_user import CreateUserUseCase
from src.modules.users.application.use_cases.delete_user import DeleteUserUseCase
from src.modules.users.application.use_cases.get_current_user import GetCurrentUserUseCase
from src.modules.users.application.use_cases.get_lead_owners import GetLeadOwnersUseCase
from src.modules.users.application.use_cases.get_user_details import GetUserDetailsUseCase
from src.modules.users.application.use_cases.get_user_deletion_preview import (
    GetUserDeletionPreviewUseCase,
)
from src.modules.users.application.use_cases.get_replacement_candidates import (
    GetReplacementCandidatesUseCase,
)
from src.modules.users.application.use_cases.get_users import GetUsersUseCase
from src.modules.users.application.use_cases.get_user_audit_logs import (
    GetUserAuditLogsUseCase,
)
from src.modules.users.application.use_cases.reset_user_password import (
    ResetUserPasswordUseCase,
)
from src.modules.users.application.use_cases.unblock_user import UnblockUserUseCase
from src.modules.users.application.use_cases.update_user import UpdateUserUseCase
from src.modules.users.infrastructure.persistence.user_audit_log_repository import (
    DjangoUserAuditLogRepository,
)
from src.modules.users.infrastructure.security.jwt_session_revoker import (
    JWTSessionRevoker,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


def get_user_repository() -> DjangoUserRepository:
    return DjangoUserRepository()


def get_current_user_use_case() -> GetCurrentUserUseCase:
    return GetCurrentUserUseCase(
        user_repository=get_user_repository(),
    )


def get_user_audit_log_repository() -> DjangoUserAuditLogRepository:
    return DjangoUserAuditLogRepository()


def get_session_revoker() -> JWTSessionRevoker:
    return JWTSessionRevoker()


def get_create_user_use_case() -> CreateUserUseCase:
    return CreateUserUseCase(
        user_repository=get_user_repository(),
        audit_log_repository=get_user_audit_log_repository(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_users_use_case() -> GetUsersUseCase:
    return GetUsersUseCase(
        user_repository=get_user_repository(),
    )


def get_user_details_use_case() -> GetUserDetailsUseCase:
    return GetUserDetailsUseCase(
        user_repository=get_user_repository(),
    )


def get_update_user_use_case() -> UpdateUserUseCase:
    return UpdateUserUseCase(
        user_repository=get_user_repository(),
        audit_log_repository=get_user_audit_log_repository(),
        session_revoker=get_session_revoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_block_user_use_case() -> BlockUserUseCase:
    return BlockUserUseCase(
        user_repository=get_user_repository(),
        audit_log_repository=get_user_audit_log_repository(),
        session_revoker=get_session_revoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_unblock_user_use_case() -> UnblockUserUseCase:
    return UnblockUserUseCase(
        user_repository=get_user_repository(),
        audit_log_repository=get_user_audit_log_repository(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_reset_user_password_use_case() -> ResetUserPasswordUseCase:
    return ResetUserPasswordUseCase(
        user_repository=get_user_repository(),
        audit_log_repository=get_user_audit_log_repository(),
        session_revoker=get_session_revoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_user_audit_logs_use_case() -> GetUserAuditLogsUseCase:
    return GetUserAuditLogsUseCase(
        audit_log_repository=get_user_audit_log_repository(),
    )


def get_delete_user_use_case() -> DeleteUserUseCase:
    return DeleteUserUseCase(
        user_repository=get_user_repository(),
        lead_repository=DjangoLeadRepository(),
        contact_repository=DjangoContactRepository(),
        account_repository=DjangoAccountRepository(),
        meeting_repository=DjangoMeetingRepository(),
        task_repository=DjangoTaskRepository(),
        reminder_repository=DjangoReminderRepository(),
        notification_repository=DjangoNotificationRepository(),
        audit_log_repository=get_user_audit_log_repository(),
        session_revoker=get_session_revoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_user_deletion_preview_use_case() -> GetUserDeletionPreviewUseCase:
    return GetUserDeletionPreviewUseCase(
        user_repository=get_user_repository(),
        lead_repository=DjangoLeadRepository(),
        contact_repository=DjangoContactRepository(),
        account_repository=DjangoAccountRepository(),
        meeting_repository=DjangoMeetingRepository(),
        task_repository=DjangoTaskRepository(),
        reminder_repository=DjangoReminderRepository(),
        notification_repository=DjangoNotificationRepository(),
        timeline_repository=DjangoTimelineRepository(),
    )


def get_lead_owners_use_case() -> GetLeadOwnersUseCase:
    return GetLeadOwnersUseCase(
        user_repository=get_user_repository(),
    )


def get_replacement_candidates_use_case() -> GetReplacementCandidatesUseCase:
    return GetReplacementCandidatesUseCase(
        user_repository=get_user_repository(),
    )
