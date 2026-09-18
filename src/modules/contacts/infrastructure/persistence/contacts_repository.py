from datetime import date, datetime
from uuid import UUID

from django.db.models import OuterRef, Subquery

from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)
from src.modules.contacts.domain.entities.contact import Contact
from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery, PaginatedResult
from src.modules.tasks.domain.enums.task_status import TaskStatus
from src.modules.tasks.infrastructure.persistence.models import (
    DjangoTaskModel,
)

from .django_contact_model import DjangoContactModel


class DjangoContactRepository(ContactRepository):

    def save(self, contact: Contact) -> Contact:
        model, created = DjangoContactModel.objects.update_or_create(
            id=contact.id,
            defaults={
                "account_id": contact.account_id,
                "contact_owner_id": contact.contact_owner_id,
                "name": contact.name,
                "email": contact.email,
                "secondary_email": contact.secondary_email,
                "phone": contact.phone,
                "other_phone": contact.other_phone,
                "mobile": contact.mobile,
                "home_phone": contact.home_phone,
                "assistant_phone": contact.assistant_phone,
                "title": contact.title,
                "department": contact.department,
                "lead_source": contact.lead_source,
                "vendor_name": contact.vendor_name,
                "date_of_birth": contact.date_of_birth,
                "assistant": contact.assistant,
                "email_opt_out": contact.email_opt_out,
                "reporting_to_id": contact.reporting_to_id,
                "mailing_address": contact.mailing_address,
                "mailing_city": contact.mailing_city,
                "mailing_state": contact.mailing_state,
                "mailing_country": contact.mailing_country,
                "mailing_postal_code": contact.mailing_postal_code,
                "other_address": contact.other_address,
                "description": contact.description,
                "created_by_id": contact.created_by_id,
                "created_at": contact.created_at,
                "modified_by_id": contact.modified_by_id,
                "updated_at": contact.updated_at,
                "is_deleted": contact.is_deleted,
            },
        )

        return self._to_domain(model)

    def get_by_id(self, contact_id: UUID) -> Contact | None:
        try:
            model = DjangoContactModel.objects.get(
                
              id=contact_id,
              is_deleted=False,
    
            )
        except DjangoContactModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def unlink_account_contacts(
      self,
      account_id: UUID,
    ) -> None:
      DjangoContactModel.objects.filter(
          account_id=account_id,
      ).update(
          account_id=None,
      )

    def get_by_id_with_relations(
    self,
    contact_id: UUID,
) -> tuple[Contact, str | None, str | None] | None:

      try:
          model = (
              DjangoContactModel.objects
              .select_related(
                  "account",
                  "contact_owner",
              )
              .get(
                  id=contact_id,
                  is_deleted=False,
              )
          )
      except DjangoContactModel.DoesNotExist:
          return None

      return (
        self._to_domain(model),
        model.account.account_name if model.account else None,
        model.contact_owner.name if model.contact_owner else None,
    )
    

    def get_all_with_relations(
        self,
        query: ListQuery,
    ) -> PaginatedResult[
        tuple[
            Contact,
            str | None,
            str | None,
            date | None,
            str | None,
        ]
    ]:
        next_task_subquery = (
            DjangoTaskModel.objects
            .filter(
                contact_id=OuterRef("pk"),
                is_deleted=False,
            )
            .exclude(
                status=TaskStatus.COMPLETED.value,
            )
            .order_by("due_date", "created_at")
        )

        queryset = (
            DjangoContactModel.objects
            .select_related(
                "account",
                "contact_owner",
            )
            .filter(is_deleted=False)
            .annotate(
                next_task_due_date=Subquery(
                    next_task_subquery.values("due_date")[:1],
                ),
                next_task_status=Subquery(
                    next_task_subquery.values("status")[:1],
                ),
            )
        )

        queryset = self._apply_filters(queryset, query.filters)
        total = queryset.count()
        queryset = queryset.order_by("name", "id")

        offset = (query.page - 1) * query.page_size
        models = queryset[offset:offset + query.page_size]

        return PaginatedResult(
            results=[
                (
                    self._to_domain(model),
                    model.account.account_name if model.account else None,
                    model.contact_owner.name if model.contact_owner else None,
                    model.next_task_due_date,
                    model.next_task_status,
                )
                for model in models
            ],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    @staticmethod
    def _apply_filters(queryset, filters: tuple[FilterCondition, ...]):
        text_fields = {
            "name": "name",
            "email": "email",
            "secondary_email": "secondary_email",
            "phone": "phone",
            "other_phone": "other_phone",
            "mobile": "mobile",
            "home_phone": "home_phone",
            "assistant_phone": "assistant_phone",
            "title": "title",
            "department": "department",
            "lead_source": "lead_source",
            "vendor_name": "vendor_name",
            "assistant": "assistant",
            "mailing_address": "mailing_address",
            "mailing_city": "mailing_city",
            "mailing_state": "mailing_state",
            "mailing_country": "mailing_country",
            "mailing_postal_code": "mailing_postal_code",
            "other_address": "other_address",
            "description": "description",
            "account_name": "account__account_name",
            "contact_owner_name": "contact_owner__name",
        }
        date_fields = {
            "date_of_birth": "date_of_birth",
        }
        datetime_fields = {
            "created_at": "created_at",
            "updated_at": "updated_at",
        }
        uuid_fields = {
            "account_id": "account_id",
            "contact_owner_id": "contact_owner_id",
            "reporting_to_id": "reporting_to_id",
            "account": "account_id",
            "contact_owner": "contact_owner_id",
            "reporting_to": "reporting_to_id",
        }
        boolean_fields = {
            "email_opt_out": "email_opt_out",
        }

        for condition in filters:
            field = condition.field
            operator = condition.operator
            value = condition.value

            if field in text_fields:
                queryset = DjangoContactRepository._apply_text_filter(
                    queryset, text_fields[field], operator, value, field
                )
            elif field in date_fields:
                queryset = DjangoContactRepository._apply_date_filter(
                    queryset, date_fields[field], operator, value, field
                )
            elif field in datetime_fields:
                queryset = DjangoContactRepository._apply_datetime_filter(
                    queryset, datetime_fields[field], operator, value, field
                )
            elif field in uuid_fields:
                queryset = DjangoContactRepository._apply_uuid_filter(
                    queryset, uuid_fields[field], operator, value, field
                )
            elif field in boolean_fields:
                queryset = DjangoContactRepository._apply_boolean_filter(
                    queryset, boolean_fields[field], operator, value, field
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
        value = DjangoContactRepository._require_string(value, field)
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
            start = DjangoContactRepository._parse_date(value["from"], field)
            end = DjangoContactRepository._parse_date(value["to"], field)
            if start > end:
                raise ValueError(f"'from' must not be after 'to' for '{field}'.")
            return queryset.filter(**{f"{db_field}__range": (start, end)})

        parsed = DjangoContactRepository._parse_date(value, field)
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
            start = DjangoContactRepository._parse_datetime(value["from"], field)
            end = DjangoContactRepository._parse_datetime(value["to"], field)
            if start > end:
                raise ValueError(f"'from' must not be after 'to' for '{field}'.")
            return queryset.filter(**{f"{db_field}__range": (start, end)})

        parsed = DjangoContactRepository._parse_datetime(value, field)
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
            values = [parse_uuid(v) for v in value]
            lookup = {f"{db_field}__in": values}
            return queryset.filter(**lookup) if operator == "in" else queryset.exclude(**lookup)
        raise ValueError(f"Operator '{operator}' is not supported for relationship field '{field}'.")

    @staticmethod
    def _apply_boolean_filter(queryset, db_field, operator, value, field):
        if operator not in {"equals", "not_equals"} or not isinstance(value, bool):
            raise ValueError(f"Value for boolean field '{field}' must be true or false.")
        lookup = {db_field: value}
        return queryset.filter(**lookup) if operator == "equals" else queryset.exclude(**lookup)

    def get_by_account_id_with_owner(
        self,
        account_id: UUID,
    ) -> list[tuple[Contact, str | None]]:
      models = (
          DjangoContactModel.objects
          .select_related("contact_owner")
          .filter(
              account_id=account_id,
              is_deleted=False,
          )
          .order_by("name", "id")
      )

      return [
          (
              self._to_domain(model),
              model.contact_owner.name if model.contact_owner else None,
          )
          for model in models
      ]

    def find_conversion_matches(
    self,
    name: str,
    email: str | None,
    phone: str | None,
    mobile: str | None,
) -> list[Contact]:

      queryset = DjangoContactModel.objects.filter(
         is_deleted=False,
       )

      matches = queryset.filter(
          name__iexact=name,
      )

      if email:
          email_matches = queryset.filter(
              email__iexact=email,
          )

          matches = matches | email_matches

      if phone:
          phone_matches = queryset.filter(
              phone=phone,
          )

          matches = matches | phone_matches

      if mobile:
          mobile_matches = queryset.filter(
              mobile=mobile,
          )

          matches = matches | mobile_matches

      matches = matches.distinct()

      return [
          self._to_domain(model)
          for model in matches
      ]

    @staticmethod
    def _to_domain(model: DjangoContactModel) -> Contact:
        return Contact(
            id=model.id,
            account_id=model.account_id,
            contact_owner_id=model.contact_owner_id,
            name=model.name,
            email=model.email,
            secondary_email=model.secondary_email,
            phone=model.phone,
            other_phone=model.other_phone,
            mobile=model.mobile,
            home_phone=model.home_phone,
            assistant_phone=model.assistant_phone,
            title=model.title,
            department=model.department,
            lead_source=model.lead_source,
            vendor_name=model.vendor_name,
            date_of_birth=model.date_of_birth,
            assistant=model.assistant,
            email_opt_out=model.email_opt_out,
            reporting_to_id=model.reporting_to_id,
            mailing_address=model.mailing_address,
            mailing_city=model.mailing_city,
            mailing_state=model.mailing_state,
            mailing_country=model.mailing_country,
            mailing_postal_code=model.mailing_postal_code,
            other_address=model.other_address,
            description=model.description,
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            modified_by_id=model.modified_by_id,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )