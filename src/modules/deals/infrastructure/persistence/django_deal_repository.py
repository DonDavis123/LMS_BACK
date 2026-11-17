from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from src.modules.deals.application.dto.get_deal import GetDealDTO
from src.modules.deals.application.interfaces.deal_repository import (
    DealRepository,
)
from src.modules.deals.domain.entities.deal import Deal
from src.modules.deals.domain.enums.deal_stage import DealStage
from src.modules.shared.application.dto.list_query import (
    FilterCondition,
    ListQuery,
    PaginatedResult,
)
from src.modules.shared.infrastructure.persistence.ordering import (
    SortableField,
    apply_ordering,
)

from .models import DjangoDealModel


class DjangoDealRepository(DealRepository):

    RELATIONS = ("owner", "account", "contact", "source_lead")

    SORTABLE_FIELDS = {
        "name": SortableField("name", is_text=True),
        "amount": SortableField("amount"),
        "expected_close_date": SortableField("expected_close_date"),
        "stage": SortableField("stage", is_text=True),
        "probability": SortableField("probability"),
        "created_at": SortableField("created_at"),
        "owner": SortableField("owner__name", is_text=True),
    }

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoDealModel.objects.filter(company_id=self._company_id)

    def save(self, deal: Deal) -> Deal:
        model, _ = self._base_queryset().update_or_create(
            id=deal.id,
            defaults={
                "company_id": self._company_id,
                "name": deal.name,
                "amount": deal.amount,
                "expected_close_date": deal.expected_close_date,
                "stage": deal.stage.value,
                "probability": deal.probability,
                "owner_id": deal.owner_id,
                "account_id": deal.account_id,
                "contact_id": deal.contact_id,
                "source_lead_id": deal.source_lead_id,
                "lead_source": deal.lead_source,
                "description": deal.description,
                "lost_reason": deal.lost_reason,
                "closed_at": deal.closed_at,
                "created_by_id": deal.created_by_id,
                "is_deleted": deal.is_deleted,
            },
        )

        return self._to_domain(model)

    def get_by_id(self, deal_id: UUID) -> Deal | None:
        try:
            model = self._base_queryset().get(id=deal_id, is_deleted=False)
        except DjangoDealModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_by_id_with_relations(self, deal_id: UUID) -> GetDealDTO | None:
        try:
            model = (
                self._base_queryset()
                .select_related(*self.RELATIONS)
                .get(id=deal_id, is_deleted=False)
            )
        except DjangoDealModel.DoesNotExist:
            return None

        return self._to_dto(model)

    def get_all_with_relations(self, query: ListQuery) -> PaginatedResult[GetDealDTO]:
        queryset = (
            self._base_queryset()
            .select_related(*self.RELATIONS)
            .filter(is_deleted=False)
        )

        if query.search:
            queryset = queryset.filter(name__icontains=query.search)

        queryset = self._apply_filters(queryset, query.filters)
        total = queryset.count()
        queryset = apply_ordering(queryset, query, self.SORTABLE_FIELDS)

        offset = (query.page - 1) * query.page_size
        models = queryset[offset:offset + query.page_size]

        return PaginatedResult(
            results=[self._to_dto(model) for model in models],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_filters(queryset, filters: tuple[FilterCondition, ...]):
        text_fields = {"name": "name"}
        choice_fields = {"stage": "stage"}
        date_fields = {"expected_close_date": "expected_close_date"}
        number_fields = {"amount": "amount", "probability": "probability"}
        uuid_fields = {
            "owner": "owner_id",
            "account": "account_id",
            "contact": "contact_id",
        }

        for condition in filters:
            field = condition.field
            operator = condition.operator
            value = condition.value

            if field in text_fields:
                queryset = DjangoDealRepository._apply_text_filter(
                    queryset, text_fields[field], operator, value, field
                )
            elif field in choice_fields:
                queryset = DjangoDealRepository._apply_choice_filter(
                    queryset, choice_fields[field], operator, value, field
                )
            elif field in date_fields:
                queryset = DjangoDealRepository._apply_date_filter(
                    queryset, date_fields[field], operator, value, field
                )
            elif field in number_fields:
                queryset = DjangoDealRepository._apply_number_filter(
                    queryset, number_fields[field], operator, value, field
                )
            elif field in uuid_fields:
                queryset = DjangoDealRepository._apply_uuid_filter(
                    queryset, uuid_fields[field], operator, value, field
                )
            else:
                raise ValueError(f"Filtering is not supported for field '{field}'.")

        return queryset

    @staticmethod
    def _require_string(value, field):
        if not isinstance(value, str):
            raise ValueError(f"Value for '{field}' must be a string.")
        if not value:
            raise ValueError(f"Value for '{field}' cannot be empty.")
        return value

    @staticmethod
    def _apply_text_filter(queryset, db_field, operator, value, field):
        value = DjangoDealRepository._require_string(value, field)
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
        allowed = {stage.value for stage in DealStage}

        if operator in {"equals", "not_equals"}:
            if not isinstance(value, str) or value not in allowed:
                raise ValueError(f"Invalid value for choice field '{field}'.")
            lookup = {db_field: value}
            return queryset.filter(**lookup) if operator == "equals" else queryset.exclude(**lookup)

        if operator in {"in", "not_in"}:
            if not isinstance(value, list) or not value or any(v not in allowed for v in value):
                raise ValueError(f"Value for '{field}' must be a non-empty list of valid choices.")
            lookup = {f"{db_field}__in": value}
            return queryset.filter(**lookup) if operator == "in" else queryset.exclude(**lookup)

        raise ValueError(f"Operator '{operator}' is not supported for choice field '{field}'.")

    @staticmethod
    def _parse_date(value, field):
        if not isinstance(value, str):
            raise ValueError(f"Value for '{field}' must be an ISO date string.")
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"Invalid date value for '{field}'.")

    @staticmethod
    def _apply_date_filter(queryset, db_field, operator, value, field):
        if operator == "between":
            if not isinstance(value, dict) or "from" not in value or "to" not in value:
                raise ValueError(f"Value for '{field}' must contain 'from' and 'to'.")
            start = DjangoDealRepository._parse_date(value["from"], field)
            end = DjangoDealRepository._parse_date(value["to"], field)
            if start > end:
                raise ValueError(f"'from' must not be after 'to' for '{field}'.")
            return queryset.filter(**{f"{db_field}__range": (start, end)})

        parsed = DjangoDealRepository._parse_date(value, field)
        if operator == "equals":
            return queryset.filter(**{db_field: parsed})
        if operator == "before":
            return queryset.filter(**{f"{db_field}__lt": parsed})
        if operator == "after":
            return queryset.filter(**{f"{db_field}__gt": parsed})
        raise ValueError(f"Operator '{operator}' is not supported for date field '{field}'.")

    @staticmethod
    def _parse_number(value, field):
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"Value for '{field}' must be a number.")
        try:
            number = Decimal(str(value).strip())
        except InvalidOperation:
            raise ValueError(f"Invalid number value for '{field}'.")
        if not number.is_finite():
            raise ValueError(f"Invalid number value for '{field}'.")
        return number

    @staticmethod
    def _apply_number_filter(queryset, db_field, operator, value, field):
        if operator == "between":
            if not isinstance(value, dict) or "from" not in value or "to" not in value:
                raise ValueError(f"Value for '{field}' must contain 'from' and 'to'.")
            start = DjangoDealRepository._parse_number(value["from"], field)
            end = DjangoDealRepository._parse_number(value["to"], field)
            if start > end:
                raise ValueError(f"'from' must not be after 'to' for '{field}'.")
            return queryset.filter(**{f"{db_field}__range": (start, end)})

        parsed = DjangoDealRepository._parse_number(value, field)
        if operator == "equals":
            return queryset.filter(**{db_field: parsed})
        if operator == "greater_than":
            return queryset.filter(**{f"{db_field}__gt": parsed})
        if operator == "less_than":
            return queryset.filter(**{f"{db_field}__lt": parsed})
        raise ValueError(f"Operator '{operator}' is not supported for number field '{field}'.")

    @staticmethod
    def _apply_uuid_filter(queryset, db_field, operator, value, field):
        def parse_uuid(item):
            try:
                return UUID(str(item))
            except (ValueError, AttributeError):
                raise ValueError(f"Invalid UUID value for '{field}'.")

        if operator in {"equals", "not_equals"}:
            parsed = parse_uuid(value)
            lookup = {db_field: parsed}
            return queryset.filter(**lookup) if operator == "equals" else queryset.exclude(**lookup)

        if operator in {"in", "not_in"}:
            if not isinstance(value, list) or not value:
                raise ValueError(f"Value for '{field}' must be a non-empty list.")
            values = [parse_uuid(item) for item in value]
            lookup = {f"{db_field}__in": values}
            return queryset.filter(**lookup) if operator == "in" else queryset.exclude(**lookup)

        raise ValueError(f"Operator '{operator}' is not supported for relationship field '{field}'.")

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dto(model: DjangoDealModel) -> GetDealDTO:
        return GetDealDTO(
            deal=DjangoDealRepository._to_domain(model),
            owner_name=model.owner.name if model.owner else None,
            account_name=model.account.account_name if model.account else None,
            contact_name=model.contact.name if model.contact else None,
            source_lead_name=model.source_lead.name if model.source_lead else None,
        )

    @staticmethod
    def _to_domain(model: DjangoDealModel) -> Deal:
        return Deal(
            id=model.id,
            name=model.name,
            amount=model.amount,
            expected_close_date=model.expected_close_date,
            stage=DealStage(model.stage),
            probability=model.probability,
            owner_id=model.owner_id,
            account_id=model.account_id,
            contact_id=model.contact_id,
            source_lead_id=model.source_lead_id,
            lead_source=model.lead_source,
            description=model.description,
            lost_reason=model.lost_reason,
            closed_at=model.closed_at,
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )
