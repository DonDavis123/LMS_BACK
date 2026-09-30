from uuid import UUID

from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class GetUserDetailsUseCase:

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(
        self,
        current_user: User,
        user_id: UUID,
    ) -> User:
        self._require_superadmin(current_user)

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found.")

        return user

    @staticmethod
    def _require_superadmin(current_user: User) -> None:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")
        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")
