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
from src.modules.calls.infrastructure.persistence.django_call_repository import (
    DjangoCallRepository,
)
from src.modules.shared.application.tenant_context import TenantContext
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
from src.modules.users.application.use_cases.get_assignable_users import (
    GetAssignableUsersUseCase,
)
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
from src.modules.users.infrastructure.persistence.current_user_reader import (
    DjangoCurrentUserReader,
)
from src.modules.users.infrastructure.persistence.user_audit_log_repository import (
    DjangoUserAuditLogRepository,
)
from src.modules.users.infrastructure.security.jwt_session_revoker import (
    JWTSessionRevoker,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


def get_user_repository(ctx: TenantContext) -> DjangoUserRepository:
    return DjangoUserRepository(company_id=ctx.company_id)


def get_current_user_use_case(
    ctx: TenantContext | None = None,
) -> GetCurrentUserUseCase:
    # Without a context (GET /users/me/ only) the user's own row is read
    # by id; platform superadmins have no company to scope by.
    if ctx is None:
        return GetCurrentUserUseCase(
            user_repository=DjangoCurrentUserReader(),
        )

    return GetCurrentUserUseCase(
        user_repository=get_user_repository(ctx),
    )


def get_user_audit_log_repository(
    ctx: TenantContext,
) -> DjangoUserAuditLogRepository:
    return DjangoUserAuditLogRepository(company_id=ctx.company_id)


def get_session_revoker() -> JWTSessionRevoker:
    return JWTSessionRevoker()


def get_create_user_use_case(ctx: TenantContext) -> CreateUserUseCase:
    return CreateUserUseCase(
        user_repository=get_user_repository(ctx),
        audit_log_repository=get_user_audit_log_repository(ctx),
        transaction_manager=DjangoTransactionManager(),
    )


def get_users_use_case(ctx: TenantContext) -> GetUsersUseCase:
    return GetUsersUseCase(
        user_repository=get_user_repository(ctx),
    )


def get_user_details_use_case(ctx: TenantContext) -> GetUserDetailsUseCase:
    return GetUserDetailsUseCase(
        user_repository=get_user_repository(ctx),
    )


def get_update_user_use_case(ctx: TenantContext) -> UpdateUserUseCase:
    return UpdateUserUseCase(
        user_repository=get_user_repository(ctx),
        audit_log_repository=get_user_audit_log_repository(ctx),
        session_revoker=get_session_revoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_block_user_use_case(ctx: TenantContext) -> BlockUserUseCase:
    return BlockUserUseCase(
        user_repository=get_user_repository(ctx),
        audit_log_repository=get_user_audit_log_repository(ctx),
        session_revoker=get_session_revoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_unblock_user_use_case(ctx: TenantContext) -> UnblockUserUseCase:
    return UnblockUserUseCase(
        user_repository=get_user_repository(ctx),
        audit_log_repository=get_user_audit_log_repository(ctx),
        transaction_manager=DjangoTransactionManager(),
    )


def get_reset_user_password_use_case(ctx: TenantContext) -> ResetUserPasswordUseCase:
    return ResetUserPasswordUseCase(
        user_repository=get_user_repository(ctx),
        audit_log_repository=get_user_audit_log_repository(ctx),
        session_revoker=get_session_revoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_user_audit_logs_use_case(ctx: TenantContext) -> GetUserAuditLogsUseCase:
    return GetUserAuditLogsUseCase(
        audit_log_repository=get_user_audit_log_repository(ctx),
        user_repository=get_user_repository(ctx),
    )


def get_delete_user_use_case(ctx: TenantContext) -> DeleteUserUseCase:
    return DeleteUserUseCase(
        user_repository=get_user_repository(ctx),
        lead_repository=DjangoLeadRepository(company_id=ctx.company_id),
        contact_repository=DjangoContactRepository(company_id=ctx.company_id),
        account_repository=DjangoAccountRepository(company_id=ctx.company_id),
        meeting_repository=DjangoMeetingRepository(company_id=ctx.company_id),
        task_repository=DjangoTaskRepository(company_id=ctx.company_id),
        call_repository=DjangoCallRepository(company_id=ctx.company_id),
        reminder_repository=DjangoReminderRepository(company_id=ctx.company_id),
        notification_repository=DjangoNotificationRepository(company_id=ctx.company_id),
        audit_log_repository=get_user_audit_log_repository(ctx),
        session_revoker=get_session_revoker(),
        transaction_manager=DjangoTransactionManager(),
    )


def get_user_deletion_preview_use_case(ctx: TenantContext) -> GetUserDeletionPreviewUseCase:
    return GetUserDeletionPreviewUseCase(
        user_repository=get_user_repository(ctx),
        lead_repository=DjangoLeadRepository(company_id=ctx.company_id),
        contact_repository=DjangoContactRepository(company_id=ctx.company_id),
        account_repository=DjangoAccountRepository(company_id=ctx.company_id),
        meeting_repository=DjangoMeetingRepository(company_id=ctx.company_id),
        task_repository=DjangoTaskRepository(company_id=ctx.company_id),
        call_repository=DjangoCallRepository(company_id=ctx.company_id),
        reminder_repository=DjangoReminderRepository(company_id=ctx.company_id),
        notification_repository=DjangoNotificationRepository(company_id=ctx.company_id),
        timeline_repository=DjangoTimelineRepository(company_id=ctx.company_id),
    )


def get_lead_owners_use_case(ctx: TenantContext) -> GetLeadOwnersUseCase:
    return GetLeadOwnersUseCase(
        user_repository=get_user_repository(ctx),
    )


def get_assignable_users_use_case(ctx: TenantContext) -> GetAssignableUsersUseCase:
    return GetAssignableUsersUseCase(
        user_repository=get_user_repository(ctx),
    )


def get_replacement_candidates_use_case(ctx: TenantContext) -> GetReplacementCandidatesUseCase:
    return GetReplacementCandidatesUseCase(
        user_repository=get_user_repository(ctx),
    )
