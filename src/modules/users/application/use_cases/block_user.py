from uuid import UUID

from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class BlockUserUseCase:

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(
        self,
        current_user: User,
        user_id: UUID,
    ) -> User:
        self._require_superadmin(current_user)

        if current_user.id == user_id:
            raise ValueError("A superadmin cannot block their own account.")

        target_user = self.user_repository.get_by_id(user_id)
        if target_user is None:
            raise ValueError("User not found.")

        if target_user.is_deleted:
            raise ValueError("A deleted user cannot be blocked.")

        updated_user = self.user_repository.set_active(
            user_id=user_id,
            is_active=False,
        )
        if updated_user is None:
            raise ValueError("User not found.")

        return updated_user

    @staticmethod
    def _require_superadmin(current_user: User) -> None:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")
        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")
