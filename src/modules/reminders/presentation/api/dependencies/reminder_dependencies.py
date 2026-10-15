from src.modules.shared.application.tenant_context import TenantContext
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import (
    DjangoMeetingRepository,
)
from src.modules.reminders.application.use_cases.create_reminder import (
    CreateReminderUseCase,
)
from src.modules.reminders.application.use_cases.delete_reminder import (
    DeleteReminderUseCase,
)
from src.modules.reminders.application.use_cases.get_reminder import (
    GetReminderUseCase,
)
from src.modules.reminders.application.use_cases.get_reminders import (
    GetRemindersUseCase,
)
from src.modules.reminders.application.use_cases.update_reminder import (
    UpdateReminderUseCase,
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
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


def transaction_manager():
    return DjangoTransactionManager()


def get_create_reminder_use_case(ctx: TenantContext) -> CreateReminderUseCase:
    return CreateReminderUseCase(
        DjangoReminderRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        DjangoTaskRepository(company_id=ctx.company_id),
        DjangoMeetingRepository(company_id=ctx.company_id),
        transaction_manager(),
    )


def get_get_reminder_use_case(ctx: TenantContext) -> GetReminderUseCase:
    return GetReminderUseCase(DjangoReminderRepository(company_id=ctx.company_id))


def get_get_reminders_use_case(ctx: TenantContext) -> GetRemindersUseCase:
    return GetRemindersUseCase(DjangoReminderRepository(company_id=ctx.company_id))


def get_update_reminder_use_case(ctx: TenantContext) -> UpdateReminderUseCase:
    return UpdateReminderUseCase(
        DjangoReminderRepository(company_id=ctx.company_id),
        DjangoTaskRepository(company_id=ctx.company_id),
        DjangoMeetingRepository(company_id=ctx.company_id),
        transaction_manager(),
    )


def get_delete_reminder_use_case(ctx: TenantContext) -> DeleteReminderUseCase:
    return DeleteReminderUseCase(
        DjangoReminderRepository(company_id=ctx.company_id),
        transaction_manager(),
    )
