from uuid import UUID

from src.modules.users.application.dto.assignable_users import (
    AssignableUserResponseDTO,
)
from src.modules.users.application.interfaces.user_repository import (
    UserRepository,
)


class GetAssignableUsersUseCase:

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(
        self,
        exclude_user_id: UUID | None = None,
    ) -> list[AssignableUserResponseDTO]:

        users = self.user_repository.get_assignable_users(
            exclude_user_id=exclude_user_id,
        )

        return [
            AssignableUserResponseDTO(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role.value,
            )
            for user in users
        ]
