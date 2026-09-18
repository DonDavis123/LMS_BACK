from datetime import date, datetime
from uuid import UUID

from django.db.models import Q

from src.modules.tasks.application.interfaces.task_repository import (
    TaskRepository,
)
from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery, PaginatedResult
from src.modules.tasks.domain.entities.task import Task
from src.modules.tasks.domain.enums.task_priority import TaskPriority
from src.modules.tasks.domain.enums.task_status import TaskStatus

from .models import DjangoTaskModel


class DjangoTaskRepository(TaskRepository):

    def save(self, task: Task) -> Task:
        model, created = DjangoTaskModel.objects.update_or_create(
            id=task.id,
            defaults={
                "subject": task.subject,
                "due_date": task.due_date,
                "priority": task.priority.value,
                "owner_id": task.owner_id,
                "reminder_at": task.reminder_at,
                "lead_id": task.lead_id,
                "contact_id": task.contact_id,
                "account_id": task.account_id,
                "status": task.status.value,
                "description": task.description,
                "created_by_id": task.created_by_id,
                "is_deleted": task.is_deleted,
            },
        )

        return self._to_domain(model)

    def get_by_id(self, task_id: UUID) -> Task | None:
        try:
            model = DjangoTaskModel.objects.get(id=task_id)
        except DjangoTaskModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_all(self, query: ListQuery) -> PaginatedResult[Task]:
        queryset = (
            DjangoTaskModel.objects
            .select_related(
                "owner",
                "created_by",
                "lead",
                "contact",
                "account",
            )
            .filter(is_deleted=False)
        )

        queryset = self._apply_filters(queryset, query.filters)
        total = queryset.count()
        queryset = queryset.order_by("due_date", "created_at", "id")

        offset = (query.page - 1) * query.page_size
        models = queryset[offset:offset + query.page_size]

        return PaginatedResult(
            results=[self._to_domain(model) for model in models],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    @staticmethod
    def _apply_filters(queryset, filters: tuple[FilterCondition, ...]):
        text_fields = {
            "subject": "subject",
            "contact_name": "contact__name",
        }
        choice_fields = {
            "priority": "priority",
            "status": "status",
        }
        date_fields = {
            "due_date": "due_date",
        }
        datetime_fields = {
            "created_at": "created_at",
            "updated_at": "updated_at",
        }
        uuid_fields = {
            "created_by": "created_by_id",
            "owner": "owner_id",
        }

        for condition in filters:
            field = condition.field
            operator = condition.operator
            value = condition.value

            if field in text_fields:
                queryset = DjangoTaskRepository._apply_text_filter(
                    queryset, text_fields[field], operator, value, field
                )
            elif field in choice_fields:
                queryset = DjangoTaskRepository._apply_choice_filter(
                    queryset, choice_fields[field], operator, value, field
                )
            elif field in date_fields:
                queryset = DjangoTaskRepository._apply_date_filter(
                    queryset, date_fields[field], operator, value, field
                )
            elif field in datetime_fields:
                queryset = DjangoTaskRepository._apply_datetime_filter(
                    queryset, datetime_fields[field], operator, value, field
                )
            elif field in uuid_fields:
                queryset = DjangoTaskRepository._apply_uuid_filter(
                    queryset, uuid_fields[field], operator, value, field
                )
            elif field == "related_to":
                queryset = DjangoTaskRepository._apply_related_to_filter(
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
    def _apply_text_filter(queryset, db_field, operator, value, field):
        value = DjangoTaskRepository._require_string(value, field)
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
        allowed = {key for key, _ in DjangoTaskModel._meta.get_field(db_field).choices}

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
            start = DjangoTaskRepository._parse_date(value["from"], field)
            end = DjangoTaskRepository._parse_date(value["to"], field)
            if start > end:
                raise ValueError(f"'from' must not be after 'to' for '{field}'.")
            return queryset.filter(**{f"{db_field}__range": (start, end)})

        parsed = DjangoTaskRepository._parse_date(value, field)
        if operator == "equals":
            return queryset.filter(**{db_field: parsed})
        if operator == "before":
            return queryset.filter(**{f"{db_field}__lt": parsed})
        if operator == "after":
            return queryset.filter(**{f"{db_field}__gt": parsed})
        raise ValueError(f"Operator '{operator}' is not supported for date field '{field}'.")

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
            start = DjangoTaskRepository._parse_datetime(value["from"], field)
            end = DjangoTaskRepository._parse_datetime(value["to"], field)
            if start > end:
                raise ValueError(f"'from' must not be after 'to' for '{field}'.")
            return queryset.filter(**{f"{db_field}__range": (start, end)})

        parsed = DjangoTaskRepository._parse_datetime(value, field)
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

    @staticmethod
    def _apply_related_to_filter(queryset, operator, value, field):
        value = DjangoTaskRepository._require_string(value, field)
        lookups = {
            "contains": "icontains",
            "equals": "iexact",
            "starts_with": "istartswith",
            "ends_with": "iendswith",
        }
        if operator not in lookups and operator not in {"not_contains", "not_equals"}:
            raise ValueError(f"Operator '{operator}' is not supported for field '{field}'.")

        lookup = "icontains" if operator == "not_contains" else "iexact" if operator == "not_equals" else lookups[operator]
        condition = (
            Q(**{f"lead__name__{lookup}": value})
            | Q(**{f"contact__name__{lookup}": value})
            | Q(**{f"account__account_name__{lookup}": value})
        )
        return queryset.exclude(condition) if operator in {"not_contains", "not_equals"} else queryset.filter(condition)

    def soft_delete_by_lead_id(self, lead_id: UUID) -> None:
        DjangoTaskModel.objects.filter(
            lead_id=lead_id,
            is_deleted=False,
        ).update(
            is_deleted=True,
        )

    def soft_delete_by_contact_id(self, contact_id: UUID) -> None:
        DjangoTaskModel.objects.filter(
            contact_id=contact_id,
            is_deleted=False,
        ).update(
            is_deleted=True,
        )

    def soft_delete_by_account_id(self, account_id: UUID) -> None:
        # Account-only tasks are not valid in the current Task business rules.
        # Keep this repository operation defensive for any legacy/invalid rows.
        DjangoTaskModel.objects.filter(
            account_id=account_id,
            contact_id__isnull=True,
            lead_id__isnull=True,
            is_deleted=False,
        ).update(
            is_deleted=True,
        )

    def unlink_account_from_contact_tasks(self, account_id: UUID) -> None:
        # Account is optional when a Task is associated with a Contact.
        # Deleting the Account must not destroy that Contact task.
        DjangoTaskModel.objects.filter(
            account_id=account_id,
            contact_id__isnull=False,
            is_deleted=False,
        ).update(
            account_id=None,
        )

    @staticmethod
    def _to_domain(model: DjangoTaskModel) -> Task:
        return Task(
            id=model.id,
            subject=model.subject,
            due_date=model.due_date,
            priority=TaskPriority(model.priority),
            owner_id=model.owner_id,
            reminder_at=model.reminder_at,
            lead_id=model.lead_id,
            contact_id=model.contact_id,
            account_id=model.account_id,
            status=TaskStatus(model.status),
            description=model.description,
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )
