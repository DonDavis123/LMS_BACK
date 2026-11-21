from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import TruncMonth

from src.modules.deals.application.dto.deal_board import (
    DealBoardColumnDTO,
    DealBoardQuery,
    DealCardDTO,
)
from src.modules.deals.application.dto.deal_forecast import (
    DealForecastDTO,
    MonthForecastDTO,
    StageForecastDTO,
)
from src.modules.deals.application.dto.get_deal import GetDealDTO
from src.modules.deals.application.interfaces.deal_repository import (
    DealRepository,
)
from src.modules.deals.application.services.deal_money import to_money
from src.modules.deals.domain.entities.deal import Deal
from src.modules.deals.domain.enums.deal_stage import (
    CLOSED_STAGES,
    DEFAULT_PROBABILITY,
    OPEN_STAGES,
    DealStage,
)
from src.modules.shared.application.dto.list_query import (
    FilterCondition,
    ListQuery,
    PaginatedResult,
)
from src.modules.shared.infrastructure.caching import count_cache
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
        # Every condition that narrows the queryset above is part of the cache key.
        total = count_cache.get_or_count(
            self._company_id,
            count_cache.DEALS,
            count_cache.build_filter_parts(
                query.search,
                query.filters,
                is_deleted=False,
            ),
            queryset.count,
        )
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
    # Board
    # ------------------------------------------------------------------

    def get_board(
        self,
        query: DealBoardQuery,
        closed_since: datetime,
        card_limit: int,
    ) -> list[DealBoardColumnDTO]:
        deals = self._base_queryset().filter(is_deleted=False)

        if query.owner_id is not None:
            deals = deals.filter(owner_id=query.owner_id)

        if query.search:
            deals = deals.filter(name__icontains=query.search)

        if query.expected_close_from is not None:
            deals = deals.filter(expected_close_date__gte=query.expected_close_from)

        if query.expected_close_to is not None:
            deals = deals.filter(expected_close_date__lte=query.expected_close_to)

        # Open deals are always shown; Won / Lost only when closed recently.
        visible = deals.filter(
            Q(stage__in=self._values(OPEN_STAGES))
            | Q(stage__in=self._values(CLOSED_STAGES), closed_at__gte=closed_since)
        )

        # 1 query: count and totals of every column.
        totals = {
            row["stage"]: row
            for row in visible.order_by()
            .values("stage")
            .annotate(
                count=Count("id"),
                total=Sum("amount"),
                weighted=self._weighted_sum(),
            )
        }

        columns = []

        # 1 query per column: the capped cards (select_related, so no N+1).
        for stage in DealStage:
            row = totals.get(stage.value)
            count = row["count"] if row else 0

            cards = [
                self._to_card(model)
                for model in self._column_queryset(visible, stage)[:card_limit]
            ]

            columns.append(
                DealBoardColumnDTO(
                    stage=stage,
                    default_probability=DEFAULT_PROBABILITY[stage],
                    count=count,
                    total_amount=to_money(row["total"] if row else None),
                    weighted_amount=to_money(row["weighted"] if row else None),
                    has_more=count > len(cards),
                    deals=cards,
                )
            )

        return columns

    @staticmethod
    def _column_queryset(visible, stage: DealStage):
        queryset = (
            visible.filter(stage=stage.value)
            .select_related("owner", "account", "contact")
        )

        if stage in CLOSED_STAGES:
            # Most recently closed first.
            return queryset.order_by(
                F("closed_at").desc(nulls_last=True), "-created_at", "-id"
            )

        # Soonest expected close date first, deals without a date last.
        return queryset.order_by(
            F("expected_close_date").asc(nulls_last=True), "created_at", "id"
        )

    @staticmethod
    def _to_card(model: DjangoDealModel) -> DealCardDTO:
        return DealCardDTO(
            id=model.id,
            name=model.name,
            amount=model.amount,
            expected_close_date=model.expected_close_date,
            probability=model.probability,
            owner_id=model.owner_id,
            owner_name=model.owner.name if model.owner else None,
            account_id=model.account_id,
            account_name=model.account.account_name if model.account else None,
            contact_id=model.contact_id,
            contact_name=model.contact.name if model.contact else None,
        )

    # ------------------------------------------------------------------
    # Forecast
    # ------------------------------------------------------------------

    def get_forecast(
        self,
        owner_id: UUID | None,
        month_start: datetime,
        month_end: datetime,
    ) -> DealForecastDTO:
        deals = self._base_queryset().filter(is_deleted=False)

        if owner_id is not None:
            deals = deals.filter(owner_id=owner_id)

        open_deals = deals.filter(stage__in=self._values(OPEN_STAGES))
        closed_this_month = Q(closed_at__gte=month_start, closed_at__lt=month_end)

        # 1 query: every headline number. The weighted amount uses the deal's
        # own probability (not the stage default) and is rounded only at the end.
        headline = deals.aggregate(
            open_pipeline=Sum("amount", filter=self._open_q()),
            weighted_forecast=self._weighted_sum(filter=self._open_q()),
            open_deal_count=Count("id", filter=self._open_q()),
            won_this_month=Sum(
                "amount", filter=Q(stage=DealStage.WON.value) & closed_this_month
            ),
            lost_this_month=Sum(
                "amount", filter=Q(stage=DealStage.LOST.value) & closed_this_month
            ),
        )

        # 1 query: open stages (zero rows are filled in below).
        stage_rows = {
            row["stage"]: row
            for row in open_deals.order_by()
            .values("stage")
            .annotate(
                count=Count("id"),
                total=Sum("amount"),
                weighted=self._weighted_sum(),
            )
        }

        by_stage = []
        for stage in OPEN_STAGES:
            row = stage_rows.get(stage.value)
            by_stage.append(
                StageForecastDTO(
                    stage=stage,
                    count=row["count"] if row else 0,
                    total_amount=to_money(row["total"] if row else None),
                    weighted_amount=to_money(row["weighted"] if row else None),
                )
            )

        # 1 query: open deals grouped by expected close month.
        month_rows = (
            open_deals.order_by()
            .annotate(month=TruncMonth("expected_close_date"))
            .values("month")
            .annotate(total=Sum("amount"), weighted=self._weighted_sum())
        )

        by_month = sorted(
            (
                MonthForecastDTO(
                    month=self._month_label(row["month"]),
                    total_amount=to_money(row["total"]),
                    weighted_amount=to_money(row["weighted"]),
                )
                for row in month_rows
            ),
            # Chronological; deals without a close date (None) last.
            key=lambda item: (item.month is None, item.month or ""),
        )

        return DealForecastDTO(
            open_pipeline=to_money(headline["open_pipeline"]),
            weighted_forecast=to_money(headline["weighted_forecast"]),
            won_this_month=to_money(headline["won_this_month"]),
            lost_this_month=to_money(headline["lost_this_month"]),
            open_deal_count=headline["open_deal_count"] or 0,
            by_stage=by_stage,
            by_month=by_month,
        )

    @staticmethod
    def _values(stages) -> list[str]:
        return [stage.value for stage in stages]

    @staticmethod
    def _open_q() -> Q:
        return Q(stage__in=[stage.value for stage in OPEN_STAGES])

    @staticmethod
    def _weighted_sum(**kwargs):
        """SUM(amount * probability / 100), computed by the database."""
        return Sum(
            F("amount") * F("probability") / 100,
            output_field=DecimalField(max_digits=24, decimal_places=6),
            **kwargs,
        )

    @staticmethod
    def _month_label(month) -> str | None:
        return month.strftime("%Y-%m") if month is not None else None

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
