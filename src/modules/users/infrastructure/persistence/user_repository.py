from uuid import UUID

from src.modules.users.application.interfaces.user_repository import (
    UserRepository,
)
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User

from .models import User as DjangoUser


class DjangoUserRepository(UserRepository):

    def create(
        self,
        user: User,
        password: str,
    ) -> User:

        django_user = DjangoUser.objects.create_user(
            email=user.email,
            password=password,
            name=user.name,
            role=user.role.value,
            is_active=user.is_active,
            is_staff=False,
        )

        return self._to_domain(django_user)

    def get_by_email(
        self,
        email: str,
    ) -> User | None:

        try:
            django_user = DjangoUser.objects.get(
                email=email,
            )
        except DjangoUser.DoesNotExist:
            return None

        return self._to_domain(django_user)

    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:

        try:
            django_user = DjangoUser.objects.get(
                id=user_id,
            )
        except DjangoUser.DoesNotExist:
            return None

        return self._to_domain(django_user)

    def get_lead_owners(self) -> list[User]:

        django_users = DjangoUser.objects.filter(
            role__in=[
                DjangoUser.Role.SUPERADMIN,
                DjangoUser.Role.ADMIN,
            ],
            is_active=True,
        ).order_by("name")

        return [
            self._to_domain(django_user)
            for django_user in django_users
        ]

    @staticmethod
    def _to_domain(
        django_user: DjangoUser,
    ) -> User:

        return User(
            id=django_user.id,
            name=django_user.name,
            email=django_user.email,
            role=UserRole(django_user.role),
            is_active=django_user.is_active,
            created_at=django_user.created_at,
            updated_at=django_user.updated_at,
        )