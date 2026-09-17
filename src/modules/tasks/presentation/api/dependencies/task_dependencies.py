from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)
from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.tasks.application.use_cases.create_task import (
    CreateTaskUseCase,
)
from src.modules.tasks.application.use_cases.delete_task import (
    DeleteTaskUseCase,
)
from src.modules.tasks.application.use_cases.get_task import GetTaskUseCase
from src.modules.tasks.application.use_cases.get_tasks import GetTasksUseCase
from src.modules.tasks.application.use_cases.update_task import (
    UpdateTaskUseCase,
)
from src.modules.tasks.infrastructure.persistence.django_task_repository import (
    DjangoTaskRepository,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


def get_create_task_use_case() -> CreateTaskUseCase:
    return CreateTaskUseCase(
        task_repository=DjangoTaskRepository(),
        user_repository=DjangoUserRepository(),
        lead_repository=DjangoLeadRepository(),
        contact_repository=DjangoContactRepository(),
        account_repository=DjangoAccountRepository(),
    )


def get_task_use_case() -> GetTaskUseCase:
    return GetTaskUseCase(
        task_repository=DjangoTaskRepository(),
    )


def get_tasks_use_case() -> GetTasksUseCase:
    return GetTasksUseCase(
        task_repository=DjangoTaskRepository(),
    )


def get_update_task_use_case() -> UpdateTaskUseCase:
    return UpdateTaskUseCase(
        task_repository=DjangoTaskRepository(),
        user_repository=DjangoUserRepository(),
        lead_repository=DjangoLeadRepository(),
        contact_repository=DjangoContactRepository(),
        account_repository=DjangoAccountRepository(),
    )


def get_delete_task_use_case() -> DeleteTaskUseCase:
    return DeleteTaskUseCase(
        task_repository=DjangoTaskRepository(),
    )
