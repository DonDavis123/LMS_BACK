from src.modules.contacts.application.use_cases.create_contact import CreateContactUseCase
from src.modules.contacts.application.use_cases.get_contacts import GetContactsUseCase
from src.modules.contacts.application.use_cases.get_contact_details import GetContactDetailsUseCase
from src.modules.contacts.application.use_cases.update_contact import UpdateContactUseCase
from src.modules.contacts.application.use_cases.delete_contact import DeleteContactUseCase
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder


def recorder():
    return DefaultTimelineRecorder(DjangoTimelineRepository())


def get_create_contact_use_case() -> CreateContactUseCase:
    return CreateContactUseCase(DjangoContactRepository(), DjangoAccountRepository(), DjangoUserRepository(), recorder(), DjangoTransactionManager())


def get_contacts_use_case() -> GetContactsUseCase:
    return GetContactsUseCase(DjangoContactRepository())


def get_contact_details_use_case() -> GetContactDetailsUseCase:
    return GetContactDetailsUseCase(DjangoContactRepository())


def get_update_contact_use_case() -> UpdateContactUseCase:
    return UpdateContactUseCase(DjangoContactRepository(), DjangoAccountRepository(), DjangoUserRepository(), recorder())


def get_delete_contact_use_case() -> DeleteContactUseCase:
    return DeleteContactUseCase(DjangoContactRepository(), DjangoTaskRepository(), DjangoTimelineRepository(), DjangoTransactionManager())
