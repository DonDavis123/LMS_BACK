from collections.abc import Sequence
from uuid import UUID

from django.db.models import CharField, F, Func, Q, Value
from django.db.models.functions import Lower, Trim

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.shared.application.dto.contact_point_match import (
    KIND_EMAIL,
    KIND_PHONE,
    RECORD_ACCOUNT,
    RECORD_CONTACT,
    RECORD_LEAD,
    ContactPointMatch,
)
from src.modules.shared.application.interfaces.contact_point_directory import (
    ContactPointDirectory,
)
from src.modules.shared.application.services.contact_field_rules import (
    PHONE_MATCH_DIGITS,
    normalize_email,
    normalize_phone,
)

# (record type, model, name column, email columns, phone columns, extra filter)
_SOURCES = (
    (
        RECORD_LEAD,
        DjangoLeadModel,
        "name",
        ("email",),
        ("phone", "mobile_number"),
        {"is_deleted": False, "is_converted": False},
    ),
    (
        RECORD_CONTACT,
        DjangoContactModel,
        "name",
        ("email", "secondary_email"),
        ("phone", "mobile", "other_phone", "home_phone"),
        {"is_deleted": False},
    ),
    (
        RECORD_ACCOUNT,
        DjangoAccountModel,
        "account_name",
        (),
        ("phone",),
        {"is_deleted": False},
    ),
)


class _DigitsOnly(Func):
    """Postgres ``regexp_replace(column, '\\D', '', 'g')``."""

    function = "regexp_replace"
    output_field = CharField()

    def __init__(self, expression):
        super().__init__(
            expression,
            Value(r"\D", output_field=CharField()),
            Value("", output_field=CharField()),
            Value("g", output_field=CharField()),
        )


class DjangoContactPointDirectory(ContactPointDirectory):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def find_matches(
        self,
        *,
        emails: Sequence[str],
        phones: Sequence[str],
        exclude: tuple[str, UUID] | None = None,
    ) -> list[ContactPointMatch]:
        email_keys = {normalize_email(v): v for v in emails if normalize_email(v)}
        phone_keys = {normalize_phone(v): v for v in phones if normalize_phone(v)}
        if not email_keys and not phone_keys:
            return []

        matches: list[ContactPointMatch] = []
        for record_type, model, name_col, email_cols, phone_cols, extra in _SOURCES:
            queryset = model.objects.filter(company_id=self._company_id, **extra)
            if exclude and exclude[0] == record_type:
                queryset = queryset.exclude(id=exclude[1])

            annotations, condition = {}, Q()
            for column in email_cols:
                alias = f"_e_{column}"
                annotations[alias] = Lower(Trim(F(column)))
                if email_keys:
                    condition |= Q(**{f"{alias}__in": list(email_keys)})
            for column in phone_cols:
                alias = f"_p_{column}"
                annotations[alias] = _DigitsOnly(F(column))
                for key in phone_keys:
                    lookup = "endswith" if len(key) >= PHONE_MATCH_DIGITS else "exact"
                    condition |= Q(**{f"{alias}__{lookup}": key})
            if not condition:
                continue

            rows = queryset.annotate(**annotations).filter(condition)[:5]
            for row in rows:
                matches.extend(
                    self._describe(row, record_type, name_col, email_cols,
                                   phone_cols, email_keys, phone_keys)
                )
        return matches

    @staticmethod
    def _describe(row, record_type, name_col, email_cols, phone_cols,
                  email_keys, phone_keys):
        found = []
        name = getattr(row, name_col) or ""
        for column in email_cols:
            key = normalize_email(getattr(row, column))
            if key in email_keys:
                found.append(ContactPointMatch(
                    record_type, row.id, name, KIND_EMAIL, email_keys[key]))
        for column in phone_cols:
            key = normalize_phone(getattr(row, column))
            if key in phone_keys:
                found.append(ContactPointMatch(
                    record_type, row.id, name, KIND_PHONE, phone_keys[key]))
        return found
