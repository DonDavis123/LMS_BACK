from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify

from src.modules.companies.application.dto.company_dto import (
    CompanyAdminDTO,
    CompanyDetailDTO,
    CompanyListDTO,
)
from src.modules.companies.application.interfaces.company_repository import (
    CompanyRepository,
)
from src.modules.companies.domain.entities.company import Company
from src.modules.companies.domain.entities.company_status import CompanyStatus
from src.modules.shared.application.dto.list_query import (
    FilterCondition,
    ListQuery,
    PaginatedResult,
)
from src.modules.shared.infrastructure.persistence.ordering import (
    SortableField,
    apply_ordering,
)
from src.modules.users.infrastructure.persistence.models import User as DjangoUser

from .django_company_model import DjangoCompanyModel

SLUG_MAX_LENGTH = 100
_MAX_SLUG_ATTEMPTS = 5


class DjangoCompanyRepository(CompanyRepository):

    SORTABLE_FIELDS = {
        "name": SortableField("name", is_text=True),
        "slug": SortableField("slug", is_text=True),
        "status": SortableField("status", is_text=True),
        "created_at": SortableField("created_at"),
        "users_count": SortableField("users_count"),
    }

    @staticmethod
    def _with_users_count():
        return DjangoCompanyModel.objects.annotate(
            users_count=Count("users", filter=Q(users__deleted_at__isnull=True)),
        )

    def get_all(self, query: ListQuery) -> PaginatedResult[CompanyListDTO]:
        queryset = self._with_users_count()
        if query.search:
            queryset = queryset.filter(
                Q(name__icontains=query.search) | Q(slug__icontains=query.search)
            )
        queryset = self._apply_filters(queryset, query.filters)
        total = queryset.count()
        queryset = apply_ordering(queryset, query, self.SORTABLE_FIELDS)

        offset = (query.page - 1) * query.page_size
        models = queryset[offset:offset + query.page_size]

        return PaginatedResult(
            results=[
                CompanyListDTO(
                    id=model.id,
                    name=model.name,
                    slug=model.slug,
                    website=model.website,
                    status=CompanyStatus(model.status),
                    created_at=model.created_at,
                    users_count=model.users_count,
                )
                for model in models
            ],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    @staticmethod
    def _apply_filters(queryset, filters: tuple[FilterCondition, ...]):
        allowed = {value for value, _ in DjangoCompanyModel.Status.choices}
        for condition in filters:
            if condition.field != "status":
                raise ValueError(
                    f"Filtering is not supported for field '{condition.field}'."
                )
            operator, value = condition.operator, condition.value
            if operator in {"equals", "not_equals"}:
                if not isinstance(value, str) or value not in allowed:
                    raise ValueError("Invalid value for choice field 'status'.")
                lookup = {"status": value}
            elif operator in {"in", "not_in"}:
                if (
                    not isinstance(value, list)
                    or not value
                    or any(not isinstance(v, str) or v not in allowed for v in value)
                ):
                    raise ValueError(
                        "Value for 'status' must be a non-empty list of valid choices."
                    )
                lookup = {"status__in": value}
            else:
                raise ValueError(
                    f"Operator '{operator}' is not supported for choice field 'status'."
                )
            negate = operator in {"not_equals", "not_in"}
            queryset = queryset.exclude(**lookup) if negate else queryset.filter(**lookup)
        return queryset

    def get_by_id(self, company_id: UUID) -> Company | None:
        model = DjangoCompanyModel.objects.filter(id=company_id).first()
        return self._to_domain(model) if model else None

    def get_detail(self, company_id: UUID) -> CompanyDetailDTO | None:
        model = self._with_users_count().filter(id=company_id).first()
        if model is None:
            return None

        superadmins = DjangoUser.objects.filter(
            company_id=company_id,
            role=DjangoUser.Role.SUPERADMIN,
            deleted_at__isnull=True,
        ).order_by("name", "id")

        return CompanyDetailDTO(
            id=model.id,
            name=model.name,
            slug=model.slug,
            website=model.website,
            status=CompanyStatus(model.status),
            status_reason=model.status_reason,
            status_changed_at=model.status_changed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            users_count=model.users_count,
            superadmins=[
                CompanyAdminDTO(
                    id=user.id,
                    name=user.name,
                    email=user.email,
                    is_active=user.is_active,
                )
                for user in superadmins
            ],
        )

    def create(
        self,
        name: str,
        website: str | None,
        created_by_id: UUID,
    ) -> Company:
        base = (slugify(name) or "company")[:SLUG_MAX_LENGTH].strip("-") or "company"

        for _ in range(_MAX_SLUG_ATTEMPTS):
            slug = self._next_free_slug(base)
            try:
                with transaction.atomic():
                    model = DjangoCompanyModel.objects.create(
                        name=name,
                        slug=slug,
                        website=website,
                        status=DjangoCompanyModel.Status.ACTIVE,
                        status_changed_at=timezone.now(),
                        status_changed_by_id=created_by_id,
                        created_by_id=created_by_id,
                    )
            except IntegrityError:
                # Lost a race for the slug; pick the next free one.
                continue
            return self._to_domain(model)

        raise ValueError("Could not generate a unique company slug.")

    @staticmethod
    def _next_free_slug(base: str) -> str:
        taken = set(
            DjangoCompanyModel.objects.filter(slug__istartswith=base)
            .annotate(lower_slug=Lower("slug"))
            .values_list("lower_slug", flat=True)
        )
        if base.lower() not in taken:
            return base

        suffix = 2
        while True:
            tail = f"-{suffix}"
            candidate = f"{base[:SLUG_MAX_LENGTH - len(tail)]}{tail}"
            if candidate.lower() not in taken:
                return candidate
            suffix += 1

    def update(
        self,
        company_id: UUID,
        name: str | None,
        website: str | None,
        update_website: bool,
    ) -> Company:
        model = self._get_model(company_id)
        fields = ["updated_at"]
        if name is not None:
            model.name = name
            fields.append("name")
        if update_website:
            model.website = website
            fields.append("website")
        model.save(update_fields=fields)
        return self._to_domain(model)

    def set_status(
        self,
        company_id: UUID,
        status: CompanyStatus,
        reason: str,
        changed_by_id: UUID,
    ) -> Company:
        model = self._get_model(company_id)
        model.status = status.value
        model.status_reason = reason
        model.status_changed_at = timezone.now()
        model.status_changed_by_id = changed_by_id
        model.save(
            update_fields=[
                "status",
                "status_reason",
                "status_changed_at",
                "status_changed_by",
                "updated_at",
            ]
        )
        return self._to_domain(model)

    def email_exists(self, email: str) -> bool:
        return DjangoUser.objects.filter(email__iexact=email.strip()).exists()

    def get_user_ids(self, company_id: UUID) -> list[UUID]:
        return list(
            DjangoUser.objects.filter(company_id=company_id).values_list(
                "id", flat=True
            )
        )

    @staticmethod
    def _get_model(company_id: UUID) -> DjangoCompanyModel:
        try:
            return DjangoCompanyModel.objects.get(id=company_id)
        except DjangoCompanyModel.DoesNotExist:
            raise ValueError("Company not found.")

    @staticmethod
    def _to_domain(model: DjangoCompanyModel) -> Company:
        return Company(
            id=model.id,
            name=model.name,
            slug=model.slug,
            status=CompanyStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
            website=model.website,
            status_reason=model.status_reason,
            status_changed_at=model.status_changed_at,
            status_changed_by_id=model.status_changed_by_id,
            created_by_id=model.created_by_id,
        )
