from uuid import UUID

from src.modules.users.application.interfaces.user_repository import (
    UserRepository,
)
from src.modules.users.domain.entities.user import User


class GetCurrentUserUseCase:

    def __init__(
        self,
        user_repository: UserRepository,
    ):
        self.user_repository = user_repository

    def execute(self, user_id: UUID) -> User:
        user = self.user_repository.get_by_id(user_id)

        if not user:
            raise ValueError("User not found.")

        return user