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

        # ---------------------------------------------------------
        # 1. Validate the authenticated user's status
        # ---------------------------------------------------------

        if not current_user.is_active:
            raise ValueError(
                "Inactive users cannot create users."
            )

        # ---------------------------------------------------------
        # 2. Validate role creation permissions
        # ---------------------------------------------------------

        allowed_roles = {
            UserRole.SUPERADMIN: {
                UserRole.ADMIN,
                UserRole.SALES_MANAGER,
                UserRole.SALES_EXECUTIVE,
            },
            UserRole.ADMIN: {
                UserRole.SALES_MANAGER,
                UserRole.SALES_EXECUTIVE,
            },
            UserRole.SALES_MANAGER: set(),
            UserRole.SALES_EXECUTIVE: set(),
        }

        allowed_roles_for_current_user = allowed_roles.get(
            current_user.role,
            set(),
        )

        if role not in allowed_roles_for_current_user:
            raise ValueError(
                f"{current_user.role.value} is not allowed "
                f"to create {role.value} users."
            )

        # ---------------------------------------------------------
        # 3. Check whether the email already exists
        # ---------------------------------------------------------

        existing_user = self.user_repository.get_by_email(email)

        if existing_user:
            raise ValueError(
                "User with this email already exists."
            )

        # ---------------------------------------------------------
        # 4. Create the domain user
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # 5. Persist through the repository abstraction
        # ---------------------------------------------------------

        return self.user_repository.create(
            user=user,
            password=password,
        )