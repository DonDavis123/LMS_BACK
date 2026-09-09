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


def get_create_contact_use_case() -> CreateContactUseCase:
    contact_repository = DjangoContactRepository()
    account_repository = DjangoAccountRepository()
    user_repository = DjangoUserRepository()

    return CreateContactUseCase(
        contact_repository=contact_repository,
        account_repository=account_repository,
        user_repository=user_repository,
    )