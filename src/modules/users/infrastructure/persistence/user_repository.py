from datetime import datetime
from uuid import UUID

from django.db.models import Q

from src.modules.shared.application.dto.list_query import (
    FilterCondition,
    ListQuery,
    PaginatedResult,
)
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

    def get_lead_owners(
        self,
        exclude_user_id: UUID | None = None,
    ) -> list[User]:

        queryset = DjangoUser.objects.filter(
            role__in=[
                DjangoUser.Role.SUPERADMIN,
                DjangoUser.Role.ADMIN,
            ],
            is_active=True,
            deleted_at__isnull=True,
        )
        if exclude_user_id is not None:
            queryset = queryset.exclude(id=exclude_user_id)

        django_users = queryset.order_by("name")

        return [
            self._to_domain(django_user)
            for django_user in django_users
        ]

    def get_all(
        self,
        query: ListQuery,
    ) -> PaginatedResult[User]:
        queryset = DjangoUser.objects.filter(deleted_at__isnull=True)
        if query.search:
            queryset = queryset.filter(
                Q(name__icontains=query.search)
                | Q(email__icontains=query.search)
            )
        queryset = self._apply_filters(queryset, query.filters)
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

    @staticmethod
    def _apply_filters(queryset, filters: tuple[FilterCondition, ...]):
        text_fields = {"name": "name", "email": "email"}
        choice_fields = {"role": "role"}
        boolean_fields = {"is_active": "is_active"}

        for condition in filters:
            field = condition.field
            operator = condition.operator
            value = condition.value

            if field in text_fields:
                queryset = DjangoUserRepository._apply_text_filter(
                    queryset, text_fields[field], operator, value, field
                )
            elif field in choice_fields:
                queryset = DjangoUserRepository._apply_choice_filter(
                    queryset, choice_fields[field], operator, value, field
                )
            elif field in boolean_fields:
                queryset = DjangoUserRepository._apply_boolean_filter(
                    queryset, boolean_fields[field], operator, value, field
                )
            else:
                raise ValueError(f"Filtering is not supported for field '{field}'.")

        return queryset

    @staticmethod
    def _apply_text_filter(queryset, db_field, operator, value, field):
        if not isinstance(value, str):
            raise ValueError(f"Value for '{field}' must be a string.")
        if not value:
            raise ValueError(f"Value for '{field}' cannot be empty.")
        lookups = {
            "contains": "icontains",
            "equals": "iexact",
            "starts_with": "istartswith",
            "ends_with": "iendswith",
        }
        if operator in lookups:
            return queryset.filter(**{f"{db_field}__{lookups[operator]}": value})
        if operator in {"not_contains", "not_equals"}:
            lookup = "icontains" if operator == "not_contains" else "iexact"
            return queryset.exclude(**{f"{db_field}__{lookup}": value})
        raise ValueError(f"Operator '{operator}' is not supported for text field '{field}'.")

    @staticmethod
    def _apply_choice_filter(queryset, db_field, operator, value, field):
        allowed = {key for key, _ in DjangoUser._meta.get_field(db_field).choices}
        if operator in {"equals", "not_equals"}:
            if not isinstance(value, str) or value not in allowed:
                raise ValueError(f"Invalid value for choice field '{field}'.")
            lookup = {db_field: value}
            return queryset.filter(**lookup) if operator == "equals" else queryset.exclude(**lookup)
        if operator in {"in", "not_in"}:
            if (
                not isinstance(value, list)
                or not value
                or any(not isinstance(v, str) or v not in allowed for v in value)
            ):
                raise ValueError(f"Value for '{field}' must be a non-empty list of valid choices.")
            lookup = {f"{db_field}__in": value}
            return queryset.filter(**lookup) if operator == "in" else queryset.exclude(**lookup)
        raise ValueError(f"Operator '{operator}' is not supported for choice field '{field}'.")

    @staticmethod
    def _apply_boolean_filter(queryset, db_field, operator, value, field):
        if operator not in {"equals", "not_equals"} or not isinstance(value, bool):
            raise ValueError(f"Value for boolean field '{field}' must be true or false.")
        lookup = {db_field: value}
        return queryset.filter(**lookup) if operator == "equals" else queryset.exclude(**lookup)

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

    def set_password(
        self,
        user_id: UUID,
        password: str,
    ) -> User | None:
        try:
            django_user = DjangoUser.objects.get(id=user_id)
        except DjangoUser.DoesNotExist:
            return None

        django_user.set_password(password)
        django_user.save(update_fields=["password", "updated_at"])

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
