from src.modules.shared.application.tenant_context import TenantContext
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.leads.infrastructure.persistence.django_lead_repository import DjangoLeadRepository
from src.modules.meetings.application.use_cases.create_meeting import CreateMeetingUseCase
from src.modules.reminders.application.services.reminder_sync_service import ReminderSyncService
from src.modules.reminders.infrastructure.persistence.django_reminder_repository import DjangoReminderRepository
from src.modules.meetings.application.use_cases.delete_meeting import DeleteMeetingUseCase
from src.modules.meetings.application.use_cases.get_meeting import GetMeetingUseCase
from src.modules.meetings.application.use_cases.get_meetings import GetMeetingsUseCase
from src.modules.meetings.application.use_cases.update_meeting import UpdateMeetingUseCase
from src.modules.meetings.infrastructure.persistence.django_meeting_repository import DjangoMeetingRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository


def recorder(ctx: TenantContext):
    return DefaultTimelineRecorder(DjangoTimelineRepository(company_id=ctx.company_id))


def transaction_manager():
    return DjangoTransactionManager()


def reminder_sync_service(ctx: TenantContext):
    return ReminderSyncService(DjangoReminderRepository(company_id=ctx.company_id))


def get_create_meeting_use_case(ctx: TenantContext) -> CreateMeetingUseCase:
    return CreateMeetingUseCase(
        DjangoMeetingRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        DjangoLeadRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
        reminder_sync_service(ctx),
    )


def get_meetings_use_case(ctx: TenantContext) -> GetMeetingsUseCase:
    return GetMeetingsUseCase(DjangoMeetingRepository(company_id=ctx.company_id))


def get_meeting_use_case(ctx: TenantContext) -> GetMeetingUseCase:
    return GetMeetingUseCase(DjangoMeetingRepository(company_id=ctx.company_id))


def get_update_meeting_use_case(ctx: TenantContext) -> UpdateMeetingUseCase:
    return UpdateMeetingUseCase(
        DjangoMeetingRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        DjangoLeadRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
        reminder_sync_service(ctx),
    )


def get_delete_meeting_use_case(ctx: TenantContext) -> DeleteMeetingUseCase:
    return DeleteMeetingUseCase(
        DjangoMeetingRepository(company_id=ctx.company_id),
        recorder(ctx),
        transaction_manager(),
        reminder_sync_service(ctx),
    )
