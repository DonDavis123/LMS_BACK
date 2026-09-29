from uuid import UUID

from src.modules.accounts.application.interfaces.account_repository import (
    AccountRepository,
)
from src.modules.accounts.domain.entities.account import Account
from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery, PaginatedResult

from .django_account_model import DjangoAccountModel


class DjangoAccountRepository(AccountRepository):

    def save(self, account: Account) -> Account:
        model, created = DjangoAccountModel.objects.update_or_create(
            id=account.id,
            defaults={
                "account_owner_id": account.account_owner_id,
                "account_name": account.account_name,
                "account_site": account.account_site,
                "account_number": account.account_number,
                "account_type": account.account_type,
                "industry": account.industry,
                "annual_revenue": account.annual_revenue,
                "rating": account.rating,
                "phone": account.phone,
                "website": account.website,
                "ticker_symbol": account.ticker_symbol,
                "ownership": account.ownership,
                "employees": account.employees,
                "sic_code": account.sic_code,

                # Billing information
                "billing_address": account.billing_address,
                "billing_city": account.billing_city,
                "billing_state": account.billing_state,
                "billing_country": account.billing_country,
                "billing_postal_code": account.billing_postal_code,

                # Description
                "description": account.description,

                # Audit information
                "created_by_id": account.created_by_id,
                "created_at": account.created_at,
                "modified_by_id": account.modified_by_id,
                "updated_at": account.updated_at,

                "is_deleted": account.is_deleted,
            },
        )

        return self._to_domain(model)

    def get_by_id(
        self,
        account_id: UUID,
    ) -> Account | None:

        try:
            model = DjangoAccountModel.objects.get(
                id=account_id,
            )
        except DjangoAccountModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_all(self) -> list[Account]:

        models = DjangoAccountModel.objects.filter(
            is_deleted=False,
        )

        return [
            self._to_domain(model)
            for model in models
        ]
    def get_all_with_owner(
        self,
        query: ListQuery,
    ) -> PaginatedResult[tuple[Account, str | None]]:
        queryset = (
            DjangoAccountModel.objects
            .select_related("account_owner")
            .filter(is_deleted=False)
        )

        queryset = self._apply_filters(queryset, query.filters)
        total = queryset.count()
        queryset = queryset.order_by("account_name", "id")

        offset = (query.page - 1) * query.page_size
        models = queryset[offset:offset + query.page_size]

        return PaginatedResult(
            results=[
                (
                    self._to_domain(model),
                    model.account_owner.name if model.account_owner else None,
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
            "account_name": "account_name",
            "account_number": "account_number",
            "account_site": "account_site",
            "account_type": "account_type",
            "billing_address": "billing_address",
            "billing_city": "billing_city",
            "billing_country": "billing_country",
            "billing_state": "billing_state",
            "billing_postal_code": "billing_postal_code",
        }
        numeric_fields = {
            "annual_revenue": "annual_revenue",
        }
        uuid_fields = {
            "account_owner": "account_owner_id",
        }

        for condition in filters:
            field = condition.field
            operator = condition.operator
            value = condition.value

            if field in text_fields:
                queryset = DjangoAccountRepository._apply_text_filter(
                    queryset, text_fields[field], operator, value, field
                )
            elif field in numeric_fields:
                queryset = DjangoAccountRepository._apply_numeric_filter(
                    queryset, numeric_fields[field], operator, value, field
                )
            elif field in uuid_fields:
                queryset = DjangoAccountRepository._apply_uuid_filter(
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
        value = DjangoAccountRepository._require_string(value, field)
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
    def _apply_numeric_filter(queryset, db_field, operator, value, field):
        if operator not in {"equals", "not_equals", "in", "not_in", "before", "after"}:
            raise ValueError(f"Operator '{operator}' is not supported for numeric field '{field}'.")

        if operator in {"in", "not_in"}:
            if not isinstance(value, list) or not value:
                raise ValueError(f"Value for '{field}' must be a non-empty list.")
            values = [DjangoAccountRepository._to_number(item, field) for item in value]
            lookup = {f"{db_field}__in": values}
        else:
            number = DjangoAccountRepository._to_number(value, field)
            lookup = {db_field: number}

        if operator == "equals":
            return queryset.filter(**lookup)
        if operator == "not_equals":
            return queryset.exclude(**lookup)
        if operator == "in":
            return queryset.filter(**lookup)
        if operator == "not_in":
            return queryset.exclude(**lookup)

        lookup = {
    f"{db_field}__gt" if operator == "after" else f"{db_field}__lt": number
}
        return queryset.filter(**lookup)

    @staticmethod
    def _to_number(value, field):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Value for '{field}' must be numeric.")
        return value

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

    def get_by_id_with_owner(
    self,
    account_id: UUID,
) -> tuple[Account, str | None] | None:

      try:
          model = (
              DjangoAccountModel.objects
              .select_related("account_owner")
              .get(
                  id=account_id,
                  is_deleted=False,
              )
        )
      except DjangoAccountModel.DoesNotExist:
          return None

      return (
          self._to_domain(model),
          model.account_owner.name if model.account_owner else None,
      )

    def find_conversion_matches(
        self,
        account_name: str,
        website: str | None,
        phone: str | None,
    ) -> list[Account]:

        queryset = DjangoAccountModel.objects.filter(
            is_deleted=False,
        )

        matches = queryset.filter(
            account_name__iexact=account_name,
        )

        if website:
            website_matches = queryset.filter(
                website__iexact=website,
            )

            matches = matches | website_matches

        if phone:
            phone_matches = queryset.filter(
                phone=phone,
            )

            matches = matches | phone_matches

        matches = matches.distinct()

        return [
            self._to_domain(model)
            for model in matches
        ]

    @staticmethod
    def _to_domain(
        model: DjangoAccountModel,
    ) -> Account:

        return Account(
            id=model.id,
            account_owner_id=model.account_owner_id,
            account_name=model.account_name,
            account_site=model.account_site,
            account_number=model.account_number,
            account_type=model.account_type,
            industry=model.industry,
            annual_revenue=model.annual_revenue,
            rating=model.rating,
            phone=model.phone,
            website=model.website,
            ticker_symbol=model.ticker_symbol,
            ownership=model.ownership,
            employees=model.employees,
            sic_code=model.sic_code,

            # Billing information
            billing_address=model.billing_address,
            billing_city=model.billing_city,
            billing_state=model.billing_state,
            billing_country=model.billing_country,
            billing_postal_code=model.billing_postal_code,

            # Description
            description=model.description,

            # Audit information
            created_by_id=model.created_by_id,
            created_at=model.created_at,
            modified_by_id=model.modified_by_id,
            updated_at=model.updated_at,

            is_deleted=model.is_deleted,
        )
