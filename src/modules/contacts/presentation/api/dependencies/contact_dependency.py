from src.modules.contacts.application.use_cases.create_contact import (
    CreateContactUseCase,
)
from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)
from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)
from src.modules.contacts.application.use_cases.get_contacts import (
    GetContactsUseCase,
)
from src.modules.contacts.application.use_cases.get_contact_details import (
    GetContactDetailsUseCase,
)
from src.modules.contacts.application.use_cases.update_contact import (
    UpdateContactUseCase,
)
from src.modules.contacts.application.use_cases.delete_contact import (
    DeleteContactUseCase,
)
from src.modules.tasks.infrastructure.persistence.django_task_repository import (
    DjangoTaskRepository,
)
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)

def get_create_contact_use_case() -> CreateContactUseCase:
    contact_repository = DjangoContactRepository()
    account_repository = DjangoAccountRepository()
    user_repository = DjangoUserRepository()

    return CreateContactUseCase(
        contact_repository=contact_repository,
        account_repository=account_repository,
        user_repository=user_repository,
    )

def get_contacts_use_case() -> GetContactsUseCase:
    contact_repository = DjangoContactRepository()

    return GetContactsUseCase(
        contact_repository=contact_repository,
    )

def get_contact_details_use_case() -> GetContactDetailsUseCase:
    contact_repository = DjangoContactRepository()

    return GetContactDetailsUseCase(
        contact_repository=contact_repository,
    )

def get_update_contact_use_case() -> UpdateContactUseCase:
    contact_repository = DjangoContactRepository()
    account_repository = DjangoAccountRepository()
    user_repository = DjangoUserRepository()

    return UpdateContactUseCase(
        contact_repository=contact_repository,
        account_repository=account_repository,
        user_repository=user_repository,
    )
def get_delete_contact_use_case() -> DeleteContactUseCase:
    contact_repository = DjangoContactRepository()
    task_repository = DjangoTaskRepository()
    transaction_manager = DjangoTransactionManager()

    return DeleteContactUseCase(
        contact_repository=contact_repository,
        task_repository=task_repository,
        transaction_manager=transaction_manager,
    )