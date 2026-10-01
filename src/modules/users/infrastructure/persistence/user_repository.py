from datetime import datetime
from uuid import UUID

from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.shared.infrastructure.persistence.ordering import (
    SortableField,
    apply_ordering,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User

from .models import User as DjangoUser


class DjangoUserRepository(UserRepository):

    SORTABLE_FIELDS = {
        "name": SortableField("name", is_text=True),
        "email": SortableField("email", is_text=True),
        "role": SortableField("role", is_text=True),
        "is_active": SortableField("is_active"),
        "created_at": SortableField("created_at"),
    }

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
            deleted_at__isnull=True,
        ).order_by("name")

        return [
            self._to_domain(django_user)
            for django_user in django_users
        ]

    def get_all(
        self,
        query: ListQuery,
    ) -> PaginatedResult[User]:
        queryset = DjangoUser.objects.filter(deleted_at__isnull=True)
        total = queryset.count()
        queryset = apply_ordering(
            queryset,
            query,
            self.SORTABLE_FIELDS,
        )

        offset = (query.page - 1) * query.page_size
        models = queryset[offset:offset + query.page_size]

        return PaginatedResult(
            results=[
                self._to_domain(model)
                for model in models
            ],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    def update(
        self,
        user: User,
    ) -> User:
        try:
            django_user = DjangoUser.objects.get(id=user.id)
        except DjangoUser.DoesNotExist:
            raise ValueError("User not found.")

        django_user.name = user.name
        django_user.email = user.email
        django_user.role = user.role.value
        django_user.is_active = user.is_active
        django_user.updated_at = user.updated_at
        django_user.save(
            update_fields=[
                "name",
                "email",
                "role",
                "is_active",
                "updated_at",
            ],
        )

        return self._to_domain(django_user)

    def set_active(
        self,
        user_id: UUID,
        is_active: bool,
    ) -> User | None:
        try:
            django_user = DjangoUser.objects.get(id=user_id)
        except DjangoUser.DoesNotExist:
            return None

        django_user.is_active = is_active
        django_user.save(update_fields=["is_active", "updated_at"])

        return self._to_domain(django_user)

    def soft_delete(
        self,
        user_id: UUID,
        deleted_at: datetime,
    ) -> User | None:
        try:
            django_user = DjangoUser.objects.get(id=user_id)
        except DjangoUser.DoesNotExist:
            return None

        django_user.is_active = False
        django_user.deleted_at = deleted_at
        django_user.save(
            update_fields=["is_active", "deleted_at", "updated_at"],
        )

        return self._to_domain(django_user)

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
            deleted_at=django_user.deleted_at,
        )
