from src.modules.shared.application.tenant_context import TenantContext
from src.modules.contacts.application.use_cases.create_contact import CreateContactUseCase
from src.modules.contacts.application.use_cases.get_contacts import GetContactsUseCase
from src.modules.contacts.application.use_cases.get_contact_details import GetContactDetailsUseCase
from src.modules.contacts.application.use_cases.update_contact import UpdateContactUseCase
from src.modules.contacts.application.use_cases.delete_contact import DeleteContactUseCase
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.picklists.infrastructure.persistence.django_picklist_repository import DjangoPicklistRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder


def recorder(ctx: TenantContext):
    return DefaultTimelineRecorder(DjangoTimelineRepository(company_id=ctx.company_id))


def get_create_contact_use_case(ctx: TenantContext) -> CreateContactUseCase:
    return CreateContactUseCase(DjangoContactRepository(company_id=ctx.company_id), DjangoAccountRepository(company_id=ctx.company_id), DjangoUserRepository(company_id=ctx.company_id), recorder(ctx), DjangoTransactionManager())


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
    )

def get_delete_contact_use_case(ctx: TenantContext) -> DeleteContactUseCase:
    return DeleteContactUseCase(DjangoContactRepository(company_id=ctx.company_id), DjangoTaskRepository(company_id=ctx.company_id), DjangoTimelineRepository(company_id=ctx.company_id), DjangoTransactionManager())
