import uuid

from datetime import datetime, timezone

from src.modules.users.application.interfaces.user_repository import (
    UserRepository,
)

from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class CreateUserUseCase:

    def __init__(
        self,
        user_repository: UserRepository,
    ):
        self.user_repository = user_repository

    def execute(
        self,
        current_user: User,
        name: str,
        email: str,
        password: str,
        role: UserRole,
    ) -> User:

        if not current_user.is_active:
            raise ValueError(
                "Inactive users cannot create users."
            )

        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError(
                "Only superadmins can create users."
            )

        allowed_roles = {
            UserRole.ADMIN,
            UserRole.SALES_MANAGER,
            UserRole.SALES_EXECUTIVE,
        }

        if role not in allowed_roles:
            raise ValueError(
                f"SUPERADMIN is not allowed to create {role.value} users."
            )

        existing_user = self.user_repository.get_by_email(email.strip().lower())

        if existing_user:
            raise ValueError(
                "User with this email already exists."
            )

        now = datetime.now(timezone.utc)

        user = User(
            id=uuid.uuid4(),
            name=name.strip(),
            email=email.strip().lower(),
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        return self.user_repository.create(
            user=user,
            password=password,
        )
