from datetime import datetime, timezone

from src.modules.users.application.dto.update_user import UpdateUserDTO
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class UpdateUserUseCase:

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(
        self,
        current_user: User,
        data: UpdateUserDTO,
    ) -> User:
        self._require_superadmin(current_user)

        target_user = self.user_repository.get_by_id(data.user_id)
        if target_user is None:
            raise ValueError("User not found.")

        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise ValueError("Name cannot be empty.")
            target_user.name = name

        if data.email is not None:
            email = data.email.strip().lower()
            if not email:
                raise ValueError("Email cannot be empty.")

            existing_user = self.user_repository.get_by_email(email)
            if existing_user is not None and existing_user.id != target_user.id:
                raise ValueError("User with this email already exists.")

            target_user.email = email

        if data.role is not None:
            if not isinstance(data.role, UserRole):
                raise ValueError("Invalid user role.")
            target_user.role = data.role

        target_user.updated_at = datetime.now(timezone.utc)

        return self.user_repository.update(target_user)

    @staticmethod
    def _require_superadmin(current_user: User) -> None:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")

        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")
