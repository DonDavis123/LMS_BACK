from datetime import date, datetime
from uuid import UUID

from src.modules.calls.application.dto.get_call import GetCallDTO
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
    }

    DEFAULT_ORDERING = ("-call_start_time", "-id")

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

        queryset = self._apply_filters(queryset, query.filters)
        total = queryset.count()
        queryset = apply_ordering(
            queryset,
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
        text_fields = {
            "description": "description",
        }
        choice_fields = {
            "call_type": "call_type",
            "outcome": "outcome",
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
            elif field in datetime_fields:
                queryset = DjangoCallRepository._apply_datetime_filter(
                    queryset, datetime_fields[field], operator, value, field
                )
            elif field in uuid_fields:
                queryset = DjangoCallRepository._apply_uuid_filter(
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
        value = DjangoCallRepository._require_string(value, field)
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
    def _parse_datetime(value, field):
        if not isinstance(value, str):
            raise ValueError(f"Value for '{field}' must be an ISO date/datetime string.")
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return date.fromisoformat(value)
            except ValueError:
                raise ValueError(f"Invalid date/datetime value for '{field}'.")

    @staticmethod
    def _apply_datetime_filter(queryset, db_field, operator, value, field):
        if operator == "between":
            if not isinstance(value, dict) or "from" not in value or "to" not in value:
                raise ValueError(f"Value for '{field}' must contain 'from' and 'to'.")
            start = DjangoCallRepository._parse_datetime(value["from"], field)
            end = DjangoCallRepository._parse_datetime(value["to"], field)
            if start > end:
                raise ValueError(f"'from' must not be after 'to' for '{field}'.")
            return queryset.filter(**{f"{db_field}__range": (start, end)})

        parsed = DjangoCallRepository._parse_datetime(value, field)
        if operator == "equals":
            return queryset.filter(**{db_field: parsed})
        if operator == "before":
            return queryset.filter(**{f"{db_field}__lt": parsed})
        if operator == "after":
            return queryset.filter(**{f"{db_field}__gt": parsed})
        raise ValueError(f"Operator '{operator}' is not supported for datetime field '{field}'.")

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
