from django.conf import settings

from src.modules.shared.application.tenant_context import TenantContext
from src.modules.shared.application.services.duplicate_guard import DuplicateGuard
from src.modules.shared.infrastructure.persistence.django_contact_point_directory import DjangoContactPointDirectory
from src.modules.contacts.application.use_cases.create_contact import CreateContactUseCase
from src.modules.contacts.application.use_cases.get_contacts import GetContactsUseCase
from src.modules.contacts.application.use_cases.get_contact_details import GetContactDetailsUseCase
from src.modules.contacts.application.use_cases.update_contact import UpdateContactUseCase
from src.modules.contacts.application.use_cases.delete_contact import DeleteContactUseCase
from src.modules.contacts.application.use_cases.generate_contact_summary import GenerateContactSummaryUseCase
from src.modules.contacts.application.use_cases.get_contact_summary import GetContactSummaryUseCase
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.contacts.infrastructure.persistence.django_contact_summary_repository import DjangoContactSummaryRepository
from src.modules.contacts.infrastructure.summary.gemini_contact_summary_generator import GeminiContactSummaryGenerator, GeminiSummaryConfig
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.picklists.infrastructure.persistence.django_picklist_repository import DjangoPicklistRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.calls.infrastructure.persistence.django_call_repository import DjangoCallRepository
from src.modules.calls.infrastructure.persistence.django_call_recording_transcript_repository import DjangoCallRecordingTranscriptRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder


def recorder(ctx: TenantContext):
    return DefaultTimelineRecorder(DjangoTimelineRepository(company_id=ctx.company_id))


def get_create_contact_use_case(ctx: TenantContext) -> CreateContactUseCase:
    return CreateContactUseCase(DjangoContactRepository(company_id=ctx.company_id), DjangoAccountRepository(company_id=ctx.company_id), DjangoUserRepository(company_id=ctx.company_id), recorder(ctx), DjangoTransactionManager(), duplicate_guard=DuplicateGuard(DjangoContactPointDirectory(company_id=ctx.company_id)))


def get_contacts_use_case(ctx: TenantContext) -> GetContactsUseCase:
    return GetContactsUseCase(DjangoContactRepository(company_id=ctx.company_id))


def get_contact_details_use_case(ctx: TenantContext) -> GetContactDetailsUseCase:
    return GetContactDetailsUseCase(DjangoContactRepository(company_id=ctx.company_id))


def get_update_contact_use_case(ctx: TenantContext) -> UpdateContactUseCase:
    return UpdateContactUseCase(
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoUserRepository(company_id=ctx.company_id),
        recorder(ctx),
        DjangoTransactionManager(),
        picklist_repository=DjangoPicklistRepository(company_id=ctx.company_id),
        duplicate_guard=DuplicateGuard(DjangoContactPointDirectory(company_id=ctx.company_id)),
    )

def get_delete_contact_use_case(ctx: TenantContext) -> DeleteContactUseCase:
    return DeleteContactUseCase(DjangoContactRepository(company_id=ctx.company_id), DjangoTaskRepository(company_id=ctx.company_id), DjangoCallRepository(company_id=ctx.company_id), DjangoTimelineRepository(company_id=ctx.company_id), DjangoTransactionManager())


def get_contact_summary_generator() -> GeminiContactSummaryGenerator:
    return GeminiContactSummaryGenerator(
        GeminiSummaryConfig(
            api_key=getattr(settings, "GEMINI_API_KEY", ""),
            model=getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
            timeout_seconds=int(getattr(settings, "CONTACT_SUMMARY_TIMEOUT_SECONDS", 60)),
            summary_language=getattr(
                settings,
                "CONTACT_SUMMARY_LANGUAGE",
                getattr(settings, "CALL_TRANSCRIPTION_SUMMARY_LANGUAGE", "English"),
            ),
        )
    )


def get_generate_contact_summary_use_case(ctx: TenantContext) -> GenerateContactSummaryUseCase:
    return GenerateContactSummaryUseCase(
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoTimelineRepository(company_id=ctx.company_id),
        DjangoCallRepository(company_id=ctx.company_id),
        DjangoCallRecordingTranscriptRepository(company_id=ctx.company_id),
        get_contact_summary_generator(),
        DjangoContactSummaryRepository(company_id=ctx.company_id),
    )


def get_contact_summary_use_case(ctx: TenantContext) -> GetContactSummaryUseCase:
    return GetContactSummaryUseCase(
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoContactSummaryRepository(company_id=ctx.company_id),
    )
