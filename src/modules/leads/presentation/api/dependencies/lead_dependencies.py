from src.modules.leads.application.use_cases.create_lead import (
    CreateLeadUseCase,
)
from src.modules.leads.application.use_cases.get_leads import (
    GetLeadsUseCase,
)
from src.modules.leads.application.use_cases.get_leaddetails import (
    GetLeadDetailsUseCase,
)
from src.modules.leads.application.use_cases.update_lead import (
    UpdateLeadUseCase,
)
from src.modules.leads.application.use_cases.delete_lead import (
    DeleteLeadUseCase,
)
from src.modules.leads.application.use_cases.convert_lead import (
    ConvertLeadUseCase,
)
from src.modules.leads.application.use_cases.coversion_check import (
    ConversionCheckUseCase,
)

from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)
from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)
from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)

from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)


def get_create_lead_use_case() -> CreateLeadUseCase:
    lead_repository = DjangoLeadRepository()
    user_repository = DjangoUserRepository()

    return CreateLeadUseCase(
        lead_repository=lead_repository,
        user_repository=user_repository,
    )


def get_update_lead_use_case() -> UpdateLeadUseCase:
    lead_repository = DjangoLeadRepository()
    user_repository = DjangoUserRepository()

    return UpdateLeadUseCase(
        lead_repository=lead_repository,
        user_repository=user_repository,
    )


def get_leads_use_case() -> GetLeadsUseCase:
    lead_repository = DjangoLeadRepository()

    return GetLeadsUseCase(
        lead_repository=lead_repository,
    )


def get_lead_details_use_case() -> GetLeadDetailsUseCase:
    lead_repository = DjangoLeadRepository()

    return GetLeadDetailsUseCase(
        lead_repository=lead_repository,
    )


def get_delete_lead_use_case() -> DeleteLeadUseCase:
    lead_repository = DjangoLeadRepository()

    return DeleteLeadUseCase(
        lead_repository=lead_repository,
    )


def get_convert_lead_use_case() -> ConvertLeadUseCase:
    lead_repository = DjangoLeadRepository()
    account_repository = DjangoAccountRepository()
    contact_repository = DjangoContactRepository()
    user_repository = DjangoUserRepository()
    transaction_manager = DjangoTransactionManager()

    return ConvertLeadUseCase(
        lead_repository=lead_repository,
        account_repository=account_repository,
        contact_repository=contact_repository,
        user_repository=user_repository,
        transaction_manager=transaction_manager,
    )


def get_conversion_check_use_case() -> ConversionCheckUseCase:
    lead_repository = DjangoLeadRepository()
    account_repository = DjangoAccountRepository()
    contact_repository = DjangoContactRepository()

    return ConversionCheckUseCase(
        lead_repository=lead_repository,
        account_repository=account_repository,
        contact_repository=contact_repository,
    )