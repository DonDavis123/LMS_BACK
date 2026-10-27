from datetime import date, datetime, time, timedelta
from uuid import UUID

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.shared.application.dto.list_query import FilterCondition, ListQuery, PaginatedResult
from src.modules.shared.infrastructure.persistence.ordering import (
    SortableField,
    apply_ordering,
)

from src.modules.leads.application.interfaces.lead_repository import (
    LeadRepository,
)
from src.modules.leads.domain.entities.lead import Lead
from src.modules.leads.domain.entities.option_text import option_text

from .django_lead_model import DjangoLeadModel


class DjangoLeadRepository(LeadRepository):

    SORTABLE_FIELDS = {
        "name": SortableField("name", is_text=True),
        "company_name": SortableField("company_name", is_text=True),
        "email": SortableField("email", is_text=True),
        "phone": SortableField("phone", is_text=True),
        "lead_source": SortableField("lead_source", is_text=True),
        "lead_status": SortableField("lead_status", is_text=True),
        "owner": SortableField("owner__name", is_text=True),
        "created_at": SortableField("created_at"),
    }

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoLeadModel.objects.filter(company_id=self._company_id)

    def save(self, lead: Lead) -> Lead:
        model, created = self._base_queryset().update_or_create(
            id=lead.id,
            defaults={
                # Always the repository's own company, never the entity's.
                "company_id": self._company_id,

                # Basic information
                "name": lead.name,
                "title": lead.title,
                "company_name": lead.company_name,
                "email": lead.email,
                "mobile_number": lead.mobile_number,
                "phone": lead.phone,

                # Lead information
                "lead_source": option_text(lead.lead_source),
                "lead_status": option_text(lead.lead_status),
                "industry": option_text(lead.industry),
                "rating": option_text(lead.rating),

                # Business information
                "website": lead.website,
                "number_of_employees": lead.number_of_employees,
                "annual_revenue": lead.annual_revenue,

                # Ownership
                "owner_id": lead.owner_id,

                # Address
                "address": lead.address,
                "city": lead.city,
                "state": lead.state,
                "country": lead.country,
                "postal_code": lead.postal_code,

                # Additional information
                "description": lead.description,

                # Backend controlled lifecycle
                "is_deleted": lead.is_deleted,
                "is_converted": lead.is_converted,
            },
        )

        return self._to_domain(model)

    def get_by_id(self, lead_id: UUID) -> Lead | None:
        try:
            model = self._base_queryset().get(
                id=lead_id
            )
        except DjangoLeadModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_by_id_with_owner(
        self,
        lead_id: UUID,
    ) -> tuple[Lead, str] | None:
        try:
            model = (
                self._base_queryset()
                .select_related("owner")
                .get(id=lead_id)
            )
        except DjangoLeadModel.DoesNotExist:
            return None

        return (
            self._to_domain(model),
            model.owner.name,
        )

    def get_by_email(self, email: str) -> Lead | None:
        email = (email or "").strip()
        if not email:
            return None
        model = (
            self._base_queryset()
            .filter(email__iexact=email, is_deleted=False)
            .order_by("-created_at")
            .first()
        )
        return self._to_domain(model) if model is not None else None

    def get_all(self) -> list[Lead]:
        models = self._base_queryset().filter(
            is_deleted=False,
            is_converted=False,
        )

        return [
            self._to_domain(model)
            for model in models
        ]

    def get_all_with_owner(
        self,
        query: ListQuery,
    ) -> PaginatedResult[tuple[Lead, str]]:
        queryset = (
            self._base_queryset()
            .select_related("owner")
            .filter(
                is_deleted=False,
                is_converted=False,
            )
        )

        if query.search:
            queryset = queryset.filter(
                Q(name__icontains=query.search)
                | Q(email__icontains=query.search)
                | Q(company_name__icontains=query.search)
            )
        queryset = self._apply_filters(queryset, query.filters)
        total = queryset.count()
        queryset = apply_ordering(queryset, query, self.SORTABLE_FIELDS)

        offset = (query.page - 1) * query.page_size
        models = queryset[offset:offset + query.page_size]

        return PaginatedResult(
            results=[
                (
                    self._to_domain(model),
                    model.owner.name,
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
            "title": "title",
            "company_name": "company_name",
            "email": "email",
            "mobile_number": "mobile_number",
            "phone": "phone",
            "website": "website",
            "address": "address",
            "city": "city",
            "state": "state",
            "country": "country",
            "postal_code": "postal_code",
            "description": "description",
        }
        choice_fields = {
            "lead_source": "lead_source",
            "lead_status": "lead_status",
            "industry": "industry",
            "rating": "rating",
        }
        numeric_fields = {
            "number_of_employees": "number_of_employees",
            "annual_revenue": "annual_revenue",
        }
        datetime_fields = {
            "created_at": "created_at",
            "updated_at": "updated_at",
        }
        relationship_fields = {
            "owner": "owner_id",
        }
        boolean_fields = {
            "is_converted": "is_converted",
        }
        # Virtual fields: a Lead has no FK to Account/Contact, so these are
        # resolved through the same matching rules used by the conversion
        # check (see _apply_related_name_filter).
        related_name_fields = {"account_name", "contact_name"}

        for condition in filters:
            field = condition.field
            operator = condition.operator
            value = condition.value

            if field in text_fields:
                queryset = DjangoLeadRepository._apply_text_filter(
                    queryset, text_fields[field], operator, value, field
                )
            elif field in choice_fields:
                queryset = DjangoLeadRepository._apply_choice_filter(
                    queryset, choice_fields[field], operator, value, field
                )
            elif field in numeric_fields:
                queryset = DjangoLeadRepository._apply_numeric_filter(
                    queryset, numeric_fields[field], operator, value, field
                )
            elif field in datetime_fields:
                queryset = DjangoLeadRepository._apply_datetime_filter(
                    queryset, datetime_fields[field], operator, value, field
                )
            elif field in relationship_fields:
                queryset = DjangoLeadRepository._apply_uuid_filter(
                    queryset, relationship_fields[field], operator, value, field
                )
            elif field in boolean_fields:
                queryset = DjangoLeadRepository._apply_boolean_filter(
                    queryset, boolean_fields[field], operator, value, field
                )
            elif field in related_name_fields:
                queryset = DjangoLeadRepository._apply_related_name_filter(
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
        value = DjangoLeadRepository._require_string(value, field)
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
        # Options are editable per company, so there is no fixed list to check
        # against. Filtering on a value nobody uses simply matches nothing.
        if operator in {"equals", "not_equals"}:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Invalid value for choice field '{field}'.")
            lookup = {db_field: value}
            return queryset.filter(**lookup) if operator == "equals" else queryset.exclude(**lookup)
        if operator in {"in", "not_in"}:
            if (
                not isinstance(value, list)
                or not value
                or any(not isinstance(v, str) or not v.strip() for v in value)
            ):
                raise ValueError(f"Value for '{field}' must be a non-empty list of valid choices.")
            lookup = {f"{db_field}__in": value}
            return queryset.filter(**lookup) if operator == "in" else queryset.exclude(**lookup)
        raise ValueError(f"Operator '{operator}' is not supported for choice field '{field}'.")

    @staticmethod
    def _apply_numeric_filter(queryset, db_field, operator, value, field):
        if operator not in {"equals", "not_equals", "in", "not_in", "before", "after"}:
            raise ValueError(f"Operator '{operator}' is not supported for numeric field '{field}'.")
        if operator in {"in", "not_in"}:
            if not isinstance(value, list) or not value:
                raise ValueError(f"Value for '{field}' must be a non-empty list.")
            values = [DjangoLeadRepository._to_number(v, field) for v in value]
            lookup = {f"{db_field}__in": values}
        else:
            number = DjangoLeadRepository._to_number(value, field)
            lookup = {db_field: number}
        if operator == "equals":
            return queryset.filter(**lookup)
        if operator == "not_equals":
            return queryset.exclude(**lookup)
        if operator == "in":
            return queryset.filter(**lookup)
        if operator == "not_in":
            return queryset.exclude(**lookup)
        lookup = {f"{db_field}__gte" if operator == "after" else f"{db_field}__lte": number}
        return queryset.filter(**lookup)

    @staticmethod
    def _to_number(value, field):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Value for '{field}' must be numeric.")
        return value

    @staticmethod
    def _apply_datetime_filter(queryset, db_field, operator, value, field):
        """
        Date-only values ("YYYY-MM-DD") are treated as whole calendar days in
        the project's configured time zone; full ISO datetimes are treated as
        exact instants. Ranges are inclusive of both ends, so "on/before" and
        "between" include every record on the last day.
        """
        parse = DjangoLeadRepository._parse_datetime

        if operator == "between":
            if not isinstance(value, dict) or "from" not in value or "to" not in value:
                raise ValueError(f"Value for '{field}' must contain 'from' and 'to'.")
            start, _ = parse(value["from"], field)
            end, end_is_day = parse(value["to"], field)
            if end_is_day:
                end = DjangoLeadRepository._next_day_start(end)
            if start > end or (end_is_day and start == end):
                raise ValueError(f"'from' must not be after 'to' for '{field}'.")
            upper = f"{db_field}__lt" if end_is_day else f"{db_field}__lte"
            return queryset.filter(**{f"{db_field}__gte": start, upper: end})

        parsed, is_day = parse(value, field)
        if operator == "equals":
            if is_day:
                return queryset.filter(**{
                    f"{db_field}__gte": parsed,
                    f"{db_field}__lt": DjangoLeadRepository._next_day_start(parsed),
                })
            return queryset.filter(**{db_field: parsed})
        if operator == "after":
            return queryset.filter(**{f"{db_field}__gte": parsed})
        if operator == "before":
            if is_day:
                return queryset.filter(
                    **{f"{db_field}__lt": DjangoLeadRepository._next_day_start(parsed)}
                )
            return queryset.filter(**{f"{db_field}__lte": parsed})
        raise ValueError(f"Operator '{operator}' is not supported for date/datetime field '{field}'.")

    @staticmethod
    def _next_day_start(day_start: datetime) -> datetime:
        next_day = day_start.astimezone(timezone.get_current_timezone()).date() + timedelta(days=1)
        return timezone.make_aware(datetime.combine(next_day, time.min))

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
    def _apply_related_name_filter(queryset, operator, value, field):
        """
        Filters leads by the name of an existing, non-deleted Account/Contact
        that the lead corresponds to. A Lead stores no FK to either, so the
        correspondence uses the same rules as the conversion check:
          - Account: account_name equals the lead's company_name (iexact)
          - Contact: name equals lead name, or email / phone / mobile equal
            the lead's (blank values never match).
        Uses correlated EXISTS subqueries: one SQL query, no N+1, leads with
        no company / no match are handled by the (NOT) EXISTS semantics.
        """
        value = DjangoLeadRepository._require_string(value, field)
        lookups = {
            "contains": "icontains",
            "not_contains": "icontains",
            "equals": "iexact",
            "not_equals": "iexact",
            "starts_with": "istartswith",
            "ends_with": "iendswith",
        }
        if operator not in lookups:
            raise ValueError(f"Operator '{operator}' is not supported for field '{field}'.")
        lookup = lookups[operator]

        if field == "account_name":
            related = DjangoAccountModel.objects.filter(
                company_id=OuterRef("company_id"),
                is_deleted=False,
                account_name__iexact=OuterRef("company_name"),
            ).filter(**{f"account_name__{lookup}": value})
        else:
            corresponds = (
                Q(name__iexact=OuterRef("name"))
                | (Q(email__iexact=OuterRef("email")) & ~Q(email=""))
                | (Q(phone=OuterRef("phone")) & ~Q(phone=""))
                | (Q(mobile=OuterRef("mobile_number")) & ~Q(mobile=""))
            )
            related = DjangoContactModel.objects.filter(
                corresponds,
                company_id=OuterRef("company_id"),
                is_deleted=False,
            ).filter(**{f"name__{lookup}": value})

        if operator in {"not_contains", "not_equals"}:
            return queryset.filter(~Exists(related))
        return queryset.filter(Exists(related))

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

    def count_by_owner_id(self, owner_id: UUID) -> int:
        return self._base_queryset().filter(owner_id=owner_id).count()

    def transfer_ownership(
        self,
        from_user_id: UUID,
        to_user_id: UUID,
    ) -> int:
        # Only the owner relationship (and updated_at) changes. Soft-deleted
        # Leads are included so the retired user keeps no ownership at all.
        return self._base_queryset().filter(
            owner_id=from_user_id,
        ).update(
            owner_id=to_user_id,
            updated_at=timezone.now(),
        )

    @staticmethod
    def _to_domain(model: DjangoLeadModel) -> Lead:
        return Lead(
            # Basic information
            id=model.id,
            name=model.name,
            title=model.title,
            company_name=model.company_name,
            email=model.email,
            mobile_number=model.mobile_number,
            phone=model.phone,

            # Lead information
            lead_source=model.lead_source,
            lead_status=model.lead_status,
            industry=model.industry,
            rating=model.rating,

            # Business information
            website=model.website,
            number_of_employees=model.number_of_employees,
            annual_revenue=model.annual_revenue,

            # Ownership
            owner_id=model.owner_id,

            # Address
            address=model.address,
            city=model.city,
            state=model.state,
            country=model.country,
            postal_code=model.postal_code,

            # Additional information
            description=model.description,

            # Backend controlled lifecycle
            is_deleted=model.is_deleted,
            is_converted=model.is_converted,

            # Backend controlled timestamps
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def get_dedupe_index(self) -> dict:
        # What get_by_email does (and what this index reproduces):
        #   - tenant: self._base_queryset() -> only this company's leads;
        #   - email__iexact on the trimmed input -> case-insensitive match;
        #   - is_deleted=False -> deleted leads never match;
        #   - converted leads DO match (the caller decides what to do);
        #   - several matches -> the most recently created lead.
        # Here the same filter (company + is_deleted=False) is read once, and
        # each email is trimmed + lower-cased, so a lookup of
        # normalize_email(x) finds the lead get_by_email(x) would return.
        # Rows are read oldest first so that, for a repeated key, the newest
        # lead overwrites older ones. Only difference: exotic non-ASCII
        # letters whose upper/lower-casing is not symmetric (e.g. "ß") may
        # match differently from the database's iexact.
        # Phones are new for import (get_by_email has no phone rule): last 10
        # digits of phone or mobile_number, 7+ digits, same newest-wins rule.
        from src.modules.leads.application.services.lead_import_duplicates import (
            normalize_email,
            normalize_phone,
        )

        rows = (
            self._base_queryset()
            .filter(is_deleted=False)
            .order_by("created_at", "id")
            .values_list(
                "id", "name", "email", "phone", "mobile_number", "is_converted"
            )
            .iterator(chunk_size=2000)
        )

        emails: dict = {}
        phones: dict = {}
        for lead_id, name, email, phone, mobile, is_converted in rows:
            info = {"id": lead_id, "name": name, "is_converted": is_converted}
            email_key = normalize_email(email)
            if email_key is not None:
                emails[email_key] = info
            for raw in (phone, mobile):
                phone_key = normalize_phone(raw)
                if phone_key is not None:
                    phones[phone_key] = info

        return {"emails": emails, "phones": phones}
