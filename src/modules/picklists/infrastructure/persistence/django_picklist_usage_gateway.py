from uuid import UUID

from django.db.models import Count

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.picklists.application.interfaces.picklist_usage_gateway import (
    PicklistUsageGateway,
)

# (module, field) -> the records/columns that store that dropdown's text.
# To make another module's dropdown customisable, add its model here.
_TARGETS = {
    ("leads", "lead_source"): [(DjangoLeadModel, "lead_source")],
    ("leads", "lead_status"): [(DjangoLeadModel, "lead_status")],
    ("leads", "industry"): [(DjangoLeadModel, "industry")],
    ("leads", "rating"): [(DjangoLeadModel, "rating")],
    ("contacts", "lead_source"): [(DjangoContactModel, "lead_source")],
    ("accounts", "industry"): [(DjangoAccountModel, "industry")],
    ("accounts", "rating"): [(DjangoAccountModel, "rating")],
    ("accounts", "ownership"): [(DjangoAccountModel, "ownership")],
}


class DjangoPicklistUsageGateway(PicklistUsageGateway):
    def __init__(self, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _targets(self, module: str, field: str):
        targets = _TARGETS.get((module, field))
        if targets is None:
            raise ValueError("Unknown picklist field.")
        return targets

    def _rows(self, model, column: str):
        # ``_base_manager`` so soft-deleted and converted rows are included:
        # they still hold the text and must stay consistent on rename/replace.
        return model._base_manager.filter(company_id=self._company_id)

    def _live_rows(self, model, column: str):
        """Only the records people can actually see.

        Soft-deleted records (and leads already converted) no longer appear in
        any list, so counting them would show numbers that match nothing on
        screen and would block deleting an option over invisible records.
        """
        rows = self._rows(model, column)
        names = {field.name for field in model._meta.get_fields()}
        if "is_deleted" in names:
            rows = rows.filter(is_deleted=False)
        if "is_converted" in names:
            rows = rows.filter(is_converted=False)
        return rows

    def count_by_value(self, module: str, field: str) -> dict[str, int]:
        totals: dict[str, int] = {}
        for model, column in self._targets(module, field):
            rows = (
                self._live_rows(model, column)
                .values(column)
                .annotate(total=Count("pk"))
            )
            for row in rows:
                totals[row[column]] = totals.get(row[column], 0) + row["total"]
        return totals

    def count(self, module: str, field: str, value: str) -> int:
        return sum(
            self._live_rows(model, column).filter(**{column: value}).count()
            for model, column in self._targets(module, field)
        )

    def replace_value(
        self, module: str, field: str, old_value: str, new_value: str
    ) -> int:
        # Every row, deleted or converted too, so none is left pointing at a
        # value that no longer exists.
        changed = 0
        for model, column in self._targets(module, field):
            changed += (
                self._rows(model, column)
                .filter(**{column: old_value})
                .update(**{column: new_value})
            )
        return changed
