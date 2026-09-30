from src.modules.users.application.use_cases.block_user import BlockUserUseCase
from src.modules.users.application.use_cases.create_user import CreateUserUseCase
from src.modules.users.application.use_cases.delete_user import DeleteUserUseCase
from src.modules.users.application.use_cases.get_current_user import GetCurrentUserUseCase
from src.modules.users.application.use_cases.get_lead_owners import GetLeadOwnersUseCase
from src.modules.users.application.use_cases.get_user_details import GetUserDetailsUseCase
from src.modules.users.application.use_cases.get_users import GetUsersUseCase
from src.modules.users.application.use_cases.unblock_user import UnblockUserUseCase
from src.modules.users.application.use_cases.update_user import UpdateUserUseCase
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


def get_user_repository() -> DjangoUserRepository:
    return DjangoUserRepository()


def get_current_user_use_case() -> GetCurrentUserUseCase:
    return GetCurrentUserUseCase(
        user_repository=get_user_repository(),
    )


def get_create_user_use_case() -> CreateUserUseCase:
    return CreateUserUseCase(
        user_repository=get_user_repository(),
    )


def get_users_use_case() -> GetUsersUseCase:
    return GetUsersUseCase(
        user_repository=get_user_repository(),
    )


def get_user_details_use_case() -> GetUserDetailsUseCase:
    return GetUserDetailsUseCase(
        user_repository=get_user_repository(),
    )


def get_update_user_use_case() -> UpdateUserUseCase:
    return UpdateUserUseCase(
        user_repository=get_user_repository(),
    )


def get_block_user_use_case() -> BlockUserUseCase:
    return BlockUserUseCase(
        user_repository=get_user_repository(),
    )


def get_unblock_user_use_case() -> UnblockUserUseCase:
    return UnblockUserUseCase(
        user_repository=get_user_repository(),
    )


def get_delete_user_use_case() -> DeleteUserUseCase:
    return DeleteUserUseCase(
        user_repository=get_user_repository(),
    )

def get_lead_owners_use_case() -> GetLeadOwnersUseCase:
    return GetLeadOwnersUseCase(
        user_repository=get_user_repository(),
    )
