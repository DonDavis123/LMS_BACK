from django.conf import settings

from src.modules.shared.application.tenant_context import TenantContext
from src.modules.shared.application.services.duplicate_guard import DuplicateGuard
from src.modules.shared.infrastructure.persistence.django_contact_point_directory import DjangoContactPointDirectory
from src.modules.accounts.application.use_cases.create_account import CreateAccountUseCase
from src.modules.accounts.application.use_cases.get_accounts import GetAccountsUseCase
from src.modules.accounts.application.use_cases.get_account_details import GetAccountDetailsUseCase
from src.modules.accounts.application.use_cases.update_account import UpdateAccountUseCase
from src.modules.accounts.application.use_cases.delete_account import DeleteAccountUseCase
from src.modules.accounts.application.use_cases.add_account_document import AddAccountDocumentUseCase
from src.modules.accounts.application.use_cases.list_account_documents import ListAccountDocumentsUseCase
from src.modules.accounts.application.use_cases.update_account_document import UpdateAccountDocumentUseCase
from src.modules.accounts.application.use_cases.delete_account_document import DeleteAccountDocumentUseCase
from src.modules.accounts.application.use_cases.generate_account_summary import GenerateAccountSummaryUseCase
from src.modules.accounts.application.use_cases.get_account_summary import GetAccountSummaryUseCase
from src.modules.accounts.infrastructure.persistence.django_account_document_repository import DjangoAccountDocumentRepository
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.accounts.infrastructure.persistence.django_account_summary_repository import DjangoAccountSummaryRepository
from src.modules.accounts.infrastructure.summary.gemini_account_summary_generator import GeminiAccountSummaryGenerator, GeminiSummaryConfig
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.calls.infrastructure.persistence.django_call_repository import DjangoCallRepository
from src.modules.calls.infrastructure.persistence.django_call_recording_transcript_repository import DjangoCallRecordingTranscriptRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.picklists.infrastructure.persistence.django_picklist_repository import DjangoPicklistRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder


def recorder(ctx: TenantContext):
    return DefaultTimelineRecorder(DjangoTimelineRepository(company_id=ctx.company_id))


def get_create_account_use_case(ctx: TenantContext) -> CreateAccountUseCase:
    return CreateAccountUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        recorder(ctx),
        DjangoTransactionManager(),
        DjangoUserRepository(company_id=ctx.company_id),
        DjangoAccountDocumentRepository(company_id=ctx.company_id),
        duplicate_guard=DuplicateGuard(DjangoContactPointDirectory(company_id=ctx.company_id)),
    )


def get_accounts_use_case(ctx: TenantContext) -> GetAccountsUseCase:
    return GetAccountsUseCase(DjangoAccountRepository(company_id=ctx.company_id))


def get_account_details_use_case(ctx: TenantContext) -> GetAccountDetailsUseCase:
    return GetAccountDetailsUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoAccountDocumentRepository(company_id=ctx.company_id),
    )


def get_update_account_use_case(ctx: TenantContext) -> UpdateAccountUseCase:
    return UpdateAccountUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        recorder(ctx),
        DjangoTransactionManager(),
        picklist_repository=DjangoPicklistRepository(company_id=ctx.company_id),
        user_repository=DjangoUserRepository(company_id=ctx.company_id),
        duplicate_guard=DuplicateGuard(DjangoContactPointDirectory(company_id=ctx.company_id)),
    )


def get_delete_account_use_case(ctx: TenantContext) -> DeleteAccountUseCase:
    return DeleteAccountUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoTaskRepository(company_id=ctx.company_id),
        DjangoCallRepository(company_id=ctx.company_id),
        DjangoTimelineRepository(company_id=ctx.company_id),
        DjangoTransactionManager(),
    )


def get_add_account_document_use_case(ctx: TenantContext) -> AddAccountDocumentUseCase:
    return AddAccountDocumentUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoAccountDocumentRepository(company_id=ctx.company_id),
        recorder(ctx),
        DjangoTransactionManager(),
    )


def get_list_account_documents_use_case(ctx: TenantContext) -> ListAccountDocumentsUseCase:
    return ListAccountDocumentsUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoAccountDocumentRepository(company_id=ctx.company_id),
    )


def get_update_account_document_use_case(ctx: TenantContext) -> UpdateAccountDocumentUseCase:
    return UpdateAccountDocumentUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoAccountDocumentRepository(company_id=ctx.company_id),
        recorder(ctx),
        DjangoTransactionManager(),
    )


def get_delete_account_document_use_case(ctx: TenantContext) -> DeleteAccountDocumentUseCase:
    return DeleteAccountDocumentUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoAccountDocumentRepository(company_id=ctx.company_id),
        recorder(ctx),
        DjangoTransactionManager(),
    )


def get_account_summary_generator() -> GeminiAccountSummaryGenerator:
    return GeminiAccountSummaryGenerator(
        GeminiSummaryConfig(
            api_key=getattr(settings, "GEMINI_API_KEY", ""),
            model=getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"),
            timeout_seconds=int(getattr(settings, "ACCOUNT_SUMMARY_TIMEOUT_SECONDS", 60)),
            summary_language=getattr(
                settings,
                "ACCOUNT_SUMMARY_LANGUAGE",
                getattr(settings, "CALL_TRANSCRIPTION_SUMMARY_LANGUAGE", "English"),
            ),
        )
    )


def get_generate_account_summary_use_case(ctx: TenantContext) -> GenerateAccountSummaryUseCase:
    return GenerateAccountSummaryUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoContactRepository(company_id=ctx.company_id),
        DjangoTimelineRepository(company_id=ctx.company_id),
        DjangoCallRepository(company_id=ctx.company_id),
        DjangoCallRecordingTranscriptRepository(company_id=ctx.company_id),
        get_account_summary_generator(),
        DjangoAccountSummaryRepository(company_id=ctx.company_id),
    )


def get_account_summary_use_case(ctx: TenantContext) -> GetAccountSummaryUseCase:
    return GetAccountSummaryUseCase(
        DjangoAccountRepository(company_id=ctx.company_id),
        DjangoAccountSummaryRepository(company_id=ctx.company_id),
    )
