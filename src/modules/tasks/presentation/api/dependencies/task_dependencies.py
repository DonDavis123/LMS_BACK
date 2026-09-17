from src.modules.accounts.infrastructure.persistence.django_account_repository import DjangoAccountRepository
from src.modules.contacts.infrastructure.persistence.contacts_repository import DjangoContactRepository
from src.modules.leads.infrastructure.persistence.django_lead_repository import DjangoLeadRepository
from src.modules.tasks.application.use_cases.create_task import CreateTaskUseCase
from src.modules.tasks.application.use_cases.delete_task import DeleteTaskUseCase
from src.modules.tasks.application.use_cases.get_task import GetTaskUseCase
from src.modules.tasks.application.use_cases.get_tasks import GetTasksUseCase
from src.modules.tasks.application.use_cases.update_task import UpdateTaskUseCase
from src.modules.tasks.infrastructure.persistence.django_task_repository import DjangoTaskRepository
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository
from src.modules.timeline.infrastructure.persistence.django_timeline_repository import DjangoTimelineRepository
from src.modules.timeline.infrastructure.timeline_recorder import DefaultTimelineRecorder
from src.modules.shared.infrastructure.transactions.django_transaction_manager import DjangoTransactionManager


def recorder():
    return DefaultTimelineRecorder(DjangoTimelineRepository())


def transaction_manager():
    return DjangoTransactionManager()


def get_create_task_use_case() -> CreateTaskUseCase:
    return CreateTaskUseCase(DjangoTaskRepository(), DjangoUserRepository(), DjangoLeadRepository(), DjangoContactRepository(), DjangoAccountRepository(), recorder(), transaction_manager())


def get_task_use_case() -> GetTaskUseCase:
    return GetTaskUseCase(DjangoTaskRepository())


def get_tasks_use_case() -> GetTasksUseCase:
    return GetTasksUseCase(DjangoTaskRepository())


def get_update_task_use_case() -> UpdateTaskUseCase:
    return UpdateTaskUseCase(DjangoTaskRepository(), DjangoUserRepository(), DjangoLeadRepository(), DjangoContactRepository(), DjangoAccountRepository(), recorder())


def get_delete_task_use_case() -> DeleteTaskUseCase:
    return DeleteTaskUseCase(DjangoTaskRepository(), recorder())
