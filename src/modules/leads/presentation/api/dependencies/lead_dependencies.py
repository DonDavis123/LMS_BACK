from src.modules.leads.application.use_cases.create_lead import CreateLeadUseCase
from src.modules.leads.application.use_cases.get_leads import GetLeadsUseCase
from src.modules.leads.application.use_cases.get_leaddetails import GetLeadDetailsUseCase
from src.modules.leads.application.use_cases.update_lead import UpdateLeadUseCase
from src.modules.leads.application.use_cases.delete_lead import DeleteLeadUseCase
from src.modules.leads.application.use_cases.convert_lead import ConvertLeadUseCase
from src.modules.leads.application.use_cases.coversion_check import ConversionCheckUseCase
from src.modules.leads.infrastructure.persistence.django_lead_repository import DjangoLeadRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository
from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder


def recorder():
    return DefaultTimelineRecorder(DjangoTimelineRepository())


def get_create_lead_use_case() -> CreateLeadUseCase:
    return CreateLeadUseCase(DjangoLeadRepository(), DjangoUserRepository(), recorder(), DjangoTransactionManager())


def get_update_lead_use_case() -> UpdateLeadUseCase:
    return UpdateLeadUseCase(DjangoLeadRepository(), DjangoUserRepository(), recorder())


def get_leads_use_case() -> GetLeadsUseCase:
    return GetLeadsUseCase(DjangoLeadRepository())


def get_lead_details_use_case() -> GetLeadDetailsUseCase:
    return GetLeadDetailsUseCase(DjangoLeadRepository())


def get_delete_lead_use_case() -> DeleteLeadUseCase:
    return DeleteLeadUseCase(DjangoLeadRepository(), DjangoTaskRepository(), DjangoTransactionManager())


def get_convert_lead_use_case() -> ConvertLeadUseCase:
    return ConvertLeadUseCase(DjangoLeadRepository(), DjangoAccountRepository(), DjangoContactRepository(), DjangoUserRepository(), DjangoTransactionManager(), recorder())


def get_conversion_check_use_case() -> ConversionCheckUseCase:
    return ConversionCheckUseCase(DjangoLeadRepository(), DjangoAccountRepository(), DjangoContactRepository())
