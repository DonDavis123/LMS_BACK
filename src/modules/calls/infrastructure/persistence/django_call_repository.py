from datetime import date, datetime, time, timedelta
from uuid import UUID

from django.db.models import (
    Case,
    CharField,
    Count,
    DateTimeField,
    F,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    UUIDField,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from src.modules.calls.application.dto.get_call import GetCallDTO
from src.modules.calls.application.dto.get_call_record import GetCallRecordDTO
from src.modules.calls.application.interfaces.call_repository import (
    CallRepository,
)
from src.modules.calls.domain.entities.call import Call
from src.modules.calls.domain.enums.call_entry_method import CallEntryMethod
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType
from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery, PaginatedResult
from src.modules.shared.infrastructure.persistence.ordering import (
    SortableField,
    apply_ordering,
)

from .models import DjangoCallModel


class DjangoCallRepository(CallRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoCallModel.objects.filter(company_id=self._company_id)

    SORTABLE_FIELDS = {
        "call_start_time": SortableField("call_start_time"),
        "duration_seconds": SortableField("duration_seconds"),
        "outcome": SortableField("outcome", is_text=True),
        "call_type": SortableField("call_type", is_text=True),
        "created_at": SortableField("created_at"),
        # "Related To" column: the lead's or the contact's name. Backed by
        # the ``record_name`` annotation added by ``_with_record_name``.
        "record_name": SortableField("record_name", is_text=True),
        "owner": SortableField("owner__name", is_text=True),
        "description": SortableField("description", is_text=True),
    }

    DEFAULT_ORDERING = ("-call_start_time", "-id")

    # Columns of the one-row-per-record list. The call columns sort by the
    # record's latest call; the other two by annotations built below.
    RECORD_SORTABLE_FIELDS = {
        **SORTABLE_FIELDS,
        "call_count": SortableField("record_call_count"),
        "last_updated_at": SortableField("record_last_updated_at"),
    }

    RECORD_DEFAULT_ORDERING = ("-record_last_updated_at", "-id")

    def save(self, call: Call) -> Call:
        model, created = self._base_queryset().update_or_create(
            id=call.id,
            defaults={
                "company_id": self._company_id,
                "lead_id": call.lead_id,
                "contact_id": call.contact_id,
                "account_id": call.account_id,
                "owner_id": call.owner_id,
                "call_type": call.call_type.value,
                "outcome": call.outcome.value,
                "entry_method": call.entry_method.value,
                "call_start_time": call.call_start_time,
                "duration_seconds": call.duration_seconds,
                "description": call.description,
                "created_by_id": call.created_by_id,
                "is_deleted": call.is_deleted,
            },
        )

        return self._to_domain(model)

    def get_by_id(self, call_id: UUID) -> Call | None:
        try:
            model = self._base_queryset().get(id=call_id, is_deleted=False)
        except DjangoCallModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_by_id_with_relations(self, call_id: UUID) -> GetCallDTO | None:
        try:
            model = (
                self._base_queryset()
                .select_related("owner", "lead", "contact", "account")
                .get(id=call_id, is_deleted=False)
            )
        except DjangoCallModel.DoesNotExist:
            return None

        return self._to_dto(model)

    def get_all_with_relations(self, query: ListQuery) -> PaginatedResult[GetCallDTO]:
        queryset = (
            self._base_queryset()
            .select_related("owner", "lead", "contact", "account")
            .filter(is_deleted=False)
        )

        queryset = self._apply_search(queryset, query.search)
        queryset = self._apply_filters(queryset, query.filters)
        total = queryset.count()
        queryset = apply_ordering(
            self._with_record_name(queryset),
            query,
            self.SORTABLE_FIELDS,
            default_ordering=self.DEFAULT_ORDERING,
        )

        offset = (query.page - 1) * query.page_size
        models = queryset[offset:offset + query.page_size]

        return PaginatedResult(
            results=[self._to_dto(model) for model in models],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    def get_record_summaries(
        self,
        query: ListQuery,
    ) -> PaginatedResult[GetCallRecordDTO]:
        """One row per lead / contact instead of one row per call.

        Each call row is kept only when it is the newest call of its lead or
        contact (a call belongs to exactly one of them). The record's call
        count and last-updated time are computed over the same (searched and
        filtered) calls, so they always agree with the row that is shown.
        """
        filtered = self._apply_filters(
            self._apply_search(
                self._base_queryset().filter(is_deleted=False),
                query.search,
            ),
            query.filters,
        )

        def per_record(field: str):
            return filtered.filter(**{field: OuterRef(field)}).order_by()

        def newest_id(field: str):
            return per_record(field).order_by("-call_start_time", "-id").values("id")[:1]

        def call_count(field: str):
            return per_record(field).values(field).annotate(total=Count("id")).values("total")

        def last_updated(field: str):
            return per_record(field).values(field).annotate(latest=Max("updated_at")).values("latest")

        def by_record(builder, output_field):
            # A call has a lead XOR a contact (CheckConstraint).
            return Case(
                When(
                    Q(lead_id__isnull=False),
                    then=Subquery(builder("lead_id"), output_field=output_field),
                ),
                default=Subquery(builder("contact_id"), output_field=output_field),
                output_field=output_field,
            )

        queryset = (
            filtered.annotate(
                record_latest_call_id=by_record(newest_id, UUIDField()),
                record_call_count=Coalesce(
                    by_record(call_count, IntegerField()),
                    Value(0),
                ),
                record_last_updated_at=by_record(last_updated, DateTimeField()),
            )
            .filter(id=F("record_latest_call_id"))
            .select_related("owner", "lead", "contact", "account")
        )

        total = queryset.count()
        queryset = apply_ordering(
            self._with_record_name(queryset),
            query,
            self.RECORD_SORTABLE_FIELDS,
            default_ordering=self.RECORD_DEFAULT_ORDERING,
        )

        offset = (query.page - 1) * query.page_size
        models = queryset[offset:offset + query.page_size]

        return PaginatedResult(
            results=[self._to_record_dto(model) for model in models],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    @staticmethod
    def _with_record_name(queryset):
        """Annotate the name of the lead / contact a call belongs to.

        A call has a lead XOR a contact (CheckConstraint), so this is simply
        whichever of the two exists. Used to sort the "Related To" column.
        """
        return queryset.annotate(
            record_name=Coalesce(
                F("lead__name"),
                F("contact__name"),
                output_field=CharField(),
            )
        )

    @staticmethod
    def _apply_search(queryset, search: str | None):
        """Free-text search over what the Calls table shows.

        Matches (case-insensitive, partial) the lead / contact name, the
        account name, the owner's name and the call notes. Like filters, the
        search narrows the calls first.
        """
        if not search:
            return queryset

        return queryset.filter(
            Q(lead__name__icontains=search)
            | Q(contact__name__icontains=search)
            | Q(account__account_name__icontains=search)
            | Q(owner__name__icontains=search)
            | Q(description__icontains=search)
        )

    def _related_record_queryset(
        self,
        *,
        lead_id: UUID | None,
        contact_id: UUID | None,
    ):
        if (lead_id is None) == (contact_id is None):
            raise ValueError("Provide exactly one of lead_id or contact_id.")

        queryset = self._base_queryset().filter(is_deleted=False)

        if lead_id is not None:
            return queryset.filter(lead_id=lead_id)

        return queryset.filter(contact_id=contact_id)

    def get_by_related_record(
        self,
        *,
        lead_id: UUID | None = None,
        contact_id: UUID | None = None,
        exclude_call_id: UUID | None = None,
        limit: int = 50,
    ) -> list[GetCallDTO]:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")

        queryset = self._related_record_queryset(
            lead_id=lead_id,
            contact_id=contact_id,
        ).select_related("owner", "lead", "contact", "account")

        if exclude_call_id is not None:
            queryset = queryset.exclude(id=exclude_call_id)

        models = queryset.order_by(*self.DEFAULT_ORDERING)[:limit]

        return [self._to_dto(model) for model in models]

    def count_by_related_record(
        self,
        *,
        lead_id: UUID | None = None,
        contact_id: UUID | None = None,
    ) -> int:
        return self._related_record_queryset(
            lead_id=lead_id,
            contact_id=contact_id,
        ).count()

    @staticmethod
    def _apply_filters(queryset, filters: tuple[FilterCondition, ...]):
        # Text fields map to one or more ORM paths; a value matches when it
        # matches any of them ("record_name" is the lead's OR the contact's name).
        text_fields = {
            "description": ("description",),
            "record_name": ("lead__name", "contact__name"),
            "account_name": ("account__account_name",),
        }
        choice_fields = {
            "call_type": "call_type",
            "outcome": "outcome",
        }
        numeric_fields = {
            "duration_seconds": "duration_seconds",
        }
        datetime_fields = {
            "call_start_time": "call_start_time",
            "created_at": "created_at",
        }
        uuid_fields = {
            "lead_id": "lead_id",
            "contact_id": "contact_id",
            "account_id": "account_id",
            "owner": "owner_id",
            "created_by": "created_by_id",
        }

        for condition in filters:
            field = condition.field
            operator = condition.operator
            value = condition.value

            if field in text_fields:
                queryset = DjangoCallRepository._apply_text_filter(
                    queryset, text_fields[field], operator, value, field
                )
            elif field in choice_fields:
                queryset = DjangoCallRepository._apply_choice_filter(
                    queryset, choice_fields[field], operator, value, field
                )
            elif field in numeric_fields:
                queryset = DjangoCallRepository._apply_numeric_filter(
                    queryset, numeric_fields[field], operator, value, field
                )
            elif field in datetime_fields:
                queryset = DjangoCallRepository._apply_datetime_filter(
                    queryset, datetime_fields[field], operator, value, field
                )
            elif field in uuid_fields:
                queryset = DjangoCallRepository._apply_uuid_filter(
                    queryset, uuid_fields[field], operator, value, field
                )
            elif field == "record_type":
                queryset = DjangoCallRepository._apply_record_type_filter(
                    queryset, operator, value, field
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
    def _apply_text_filter(queryset, db_fields, operator, value, field):
        value = DjangoCallRepository._require_string(value, field)
        if isinstance(db_fields, str):
            db_fields = (db_fields,)

        lookups = {
            "contains": "icontains",
            "equals": "iexact",
            "starts_with": "istartswith",
            "ends_with": "iendswith",
        }

        def matches(lookup: str) -> Q:
            condition = Q()
            for db_field in db_fields:
                condition |= Q(**{f"{db_field}__{lookup}": value})
            return condition

        if operator in lookups:
            return queryset.filter(matches(lookups[operator]))
        if operator in {"not_contains", "not_equals"}:
            lookup = "icontains" if operator == "not_contains" else "iexact"
            return queryset.exclude(matches(lookup))
        raise ValueError(f"Operator '{operator}' is not supported for text field '{field}'.")

    @staticmethod
    def _apply_choice_filter(queryset, db_field, operator, value, field):
        allowed = {key for key, _ in DjangoCallModel._meta.get_field(db_field).choices}

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
    def _parse_datetime(value, field) -> tuple[datetime, bool]:
        """Returns (timezone-aware datetime, is_date_only)."""
        if not isinstance(value, str):
            raise ValueError(f"Value for '{field}' must be an ISO date/datetime string.")
        try:
            day = date.fromisoformat(value)
        except ValueError:
            pass
        else:
            return timezone.make_aware(datetime.combine(day, time.min)), True
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Invalid date/datetime value for '{field}'.")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed, False

    @staticmethod
    def _next_day_start(day_start: datetime) -> datetime:
        next_day = day_start.astimezone(timezone.get_current_timezone()).date() + timedelta(days=1)
        return timezone.make_aware(datetime.combine(next_day, time.min))

    @staticmethod
    def _apply_datetime_filter(queryset, db_field, operator, value, field):
        """
        Date-only values ("YYYY-MM-DD") are treated as whole calendar days in
        the project's configured time zone; full ISO datetimes are treated as
        exact instants. Ranges are inclusive of both ends, so "on/before" and
        "between" include every call on the last day.
        """
        parse = DjangoCallRepository._parse_datetime
        next_day_start = DjangoCallRepository._next_day_start

        if operator == "between":
            if not isinstance(value, dict) or "from" not in value or "to" not in value:
                raise ValueError(f"Value for '{field}' must contain 'from' and 'to'.")
            start, _ = parse(value["from"], field)
            end, end_is_day = parse(value["to"], field)
            if end_is_day:
                end = next_day_start(end)
            if start > end or (end_is_day and start == end):
                raise ValueError(f"'from' must not be after 'to' for '{field}'.")
            upper = f"{db_field}__lt" if end_is_day else f"{db_field}__lte"
            return queryset.filter(**{f"{db_field}__gte": start, upper: end})

        parsed, is_day = parse(value, field)
        if operator == "equals":
            if is_day:
                return queryset.filter(**{
                    f"{db_field}__gte": parsed,
                    f"{db_field}__lt": next_day_start(parsed),
                })
            return queryset.filter(**{db_field: parsed})
        if operator == "after":
            return queryset.filter(**{f"{db_field}__gte": parsed})
        if operator == "before":
            if is_day:
                return queryset.filter(**{f"{db_field}__lt": next_day_start(parsed)})
            return queryset.filter(**{f"{db_field}__lte": parsed})
        raise ValueError(f"Operator '{operator}' is not supported for datetime field '{field}'.")

    @staticmethod
    def _apply_numeric_filter(queryset, db_field, operator, value, field):
        if operator not in {"equals", "not_equals", "in", "not_in", "before", "after"}:
            raise ValueError(f"Operator '{operator}' is not supported for numeric field '{field}'.")

        def to_number(item):
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError(f"Value for '{field}' must be numeric.")
            return item

        if operator in {"in", "not_in"}:
            if not isinstance(value, list) or not value:
                raise ValueError(f"Value for '{field}' must be a non-empty list.")
            lookup = {f"{db_field}__in": [to_number(item) for item in value]}
            return queryset.filter(**lookup) if operator == "in" else queryset.exclude(**lookup)

        number = to_number(value)
        if operator == "equals":
            return queryset.filter(**{db_field: number})
        if operator == "not_equals":
            return queryset.exclude(**{db_field: number})
        # "after" = at least, "before" = at most (same wording as the other lists).
        suffix = "gte" if operator == "after" else "lte"
        return queryset.filter(**{f"{db_field}__{suffix}": number})

    @staticmethod
    def _apply_record_type_filter(queryset, operator, value, field):
        """Whether the call belongs to a lead or to a contact."""
        conditions = {
            "LEAD": Q(lead_id__isnull=False),
            "CONTACT": Q(contact_id__isnull=False),
        }

        if operator in {"equals", "not_equals"}:
            if not isinstance(value, str) or value not in conditions:
                raise ValueError(f"Invalid value for '{field}'; use LEAD or CONTACT.")
            condition = conditions[value]
        elif operator in {"in", "not_in"}:
            if (
                not isinstance(value, list)
                or not value
                or any(item not in conditions for item in value)
            ):
                raise ValueError(f"Value for '{field}' must be a non-empty list of LEAD / CONTACT.")
            condition = Q()
            for item in value:
                condition |= conditions[item]
        else:
            raise ValueError(f"Operator '{operator}' is not supported for field '{field}'.")

        negate = operator in {"not_equals", "not_in"}
        return queryset.exclude(condition) if negate else queryset.filter(condition)

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

    def _soft_delete_and_return_ids(self, queryset) -> list[UUID]:
        # Collect the ids first so the caller can also remove the timeline
        # events of exactly the calls that were deleted here.
        ids = list(
            queryset.filter(is_deleted=False).values_list("id", flat=True)
        )

        if ids:
            self._base_queryset().filter(
                id__in=ids,
                is_deleted=False,
            ).update(
                is_deleted=True,
            )

        return ids

    def soft_delete_by_lead_id(self, lead_id: UUID) -> list[UUID]:
        return self._soft_delete_and_return_ids(
            self._base_queryset().filter(lead_id=lead_id)
        )

    def soft_delete_by_contact_id(self, contact_id: UUID) -> list[UUID]:
        return self._soft_delete_and_return_ids(
            self._base_queryset().filter(contact_id=contact_id)
        )

    def soft_delete_by_account_id(self, account_id: UUID) -> list[UUID]:
        # A Call can only carry an account together with a contact, so
        # account-only calls cannot exist (CheckConstraint). Kept defensive,
        # like the Task repository, for any legacy/invalid rows.
        return self._soft_delete_and_return_ids(
            self._base_queryset().filter(
                account_id=account_id,
                contact_id__isnull=True,
                lead_id__isnull=True,
            )
        )

    def unlink_account_from_contact_calls(self, account_id: UUID) -> None:
        # Account is optional when a Call is associated with a Contact.
        # Deleting the Account must not destroy that Contact call.
        self._base_queryset().filter(
            account_id=account_id,
            contact_id__isnull=False,
            is_deleted=False,
        ).update(
            account_id=None,
        )

    def count_by_owner_id(self, owner_id: UUID) -> int:
        return self._base_queryset().filter(owner_id=owner_id).count()

    def delete_by_owner_id(self, owner_id: UUID) -> int:
        # Physical deletion, including already soft-deleted Calls.
        deleted, _ = self._base_queryset().filter(
            owner_id=owner_id,
        ).delete()
        return deleted

    @staticmethod
    def _to_dto(model: DjangoCallModel) -> GetCallDTO:
        return GetCallDTO(
            call=DjangoCallRepository._to_domain(model),
            lead_name=model.lead.name if model.lead else None,
            contact_name=model.contact.name if model.contact else None,
            account_name=model.account.account_name if model.account else None,
            owner_name=model.owner.name if model.owner else None,
        )

    @staticmethod
    def _to_record_dto(model: DjangoCallModel) -> GetCallRecordDTO:
        latest_call = DjangoCallRepository._to_dto(model)

        if model.lead_id:
            record_type, record_id = "LEAD", model.lead_id
            record_name = latest_call.lead_name
        else:
            record_type, record_id = "CONTACT", model.contact_id
            record_name = latest_call.contact_name

        return GetCallRecordDTO(
            record_type=record_type,
            record_id=record_id,
            record_name=record_name,
            call_count=model.record_call_count,
            last_updated_at=model.record_last_updated_at,
            latest_call=latest_call,
        )

    @staticmethod
    def _to_domain(model: DjangoCallModel) -> Call:
        return Call(
            id=model.id,
            lead_id=model.lead_id,
            contact_id=model.contact_id,
            account_id=model.account_id,
            owner_id=model.owner_id,
            call_type=CallType(model.call_type),
            outcome=CallOutcome(model.outcome),
            call_start_time=model.call_start_time,
            duration_seconds=model.duration_seconds,
            description=model.description,
            entry_method=CallEntryMethod(model.entry_method),
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )
