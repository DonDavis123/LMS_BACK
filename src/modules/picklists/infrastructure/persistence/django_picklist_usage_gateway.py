from uuid import UUID

from django.db.models import Count

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
        # ``_base_manager`` so soft-deleted and converted rows count too:
        # they still hold the text and must stay consistent.
        return model._base_manager.filter(company_id=self._company_id)

    def count_by_value(self, module: str, field: str) -> dict[str, int]:
        totals: dict[str, int] = {}
        for model, column in self._targets(module, field):
            rows = (
                self._rows(model, column)
                .values(column)
                .annotate(total=Count("pk"))
            )
            for row in rows:
                totals[row[column]] = totals.get(row[column], 0) + row["total"]
        return totals

    def count(self, module: str, field: str, value: str) -> int:
        return sum(
            self._rows(model, column).filter(**{column: value}).count()
            for model, column in self._targets(module, field)
        )

    def replace_value(
        self, module: str, field: str, old_value: str, new_value: str
    ) -> int:
        changed = 0
        for model, column in self._targets(module, field):
            changed += (
                self._rows(model, column)
                .filter(**{column: old_value})
                .update(**{column: new_value})
            )
        return changed
