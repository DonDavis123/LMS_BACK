from uuid import UUID

from django.db import IntegrityError, transaction

from src.modules.leads.application.interfaces.lead_summary_repository import (
    LeadSummaryRepository,
)
from src.modules.leads.domain.entities.lead_summary import LeadSummary

from .django_lead_summary_model import DjangoLeadSummaryModel


class DjangoLeadSummaryRepository(LeadSummaryRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoLeadSummaryModel.objects.filter(company_id=self._company_id)

    def get_by_lead_id(self, lead_id: UUID) -> LeadSummary | None:
        model = self._base_queryset().filter(lead_id=lead_id).first()

        if model is None:
            return None

        return self._to_domain(model)

    def replace_for_lead(self, summary: LeadSummary) -> LeadSummary:
        try:
            model = self._delete_then_create(summary)
        except IntegrityError:
            # Another refresh of the same lead committed between our delete
            # and our insert (one summary per lead is enforced by the
            # database). Run again: this time the winner's row is deleted
            # and ours is stored, so the latest request wins.
            model = self._delete_then_create(summary)

        return self._to_domain(model)

    def _delete_then_create(self, summary: LeadSummary) -> DjangoLeadSummaryModel:
        # One transaction (a savepoint when an outer one is open): the old
        # summary is never lost unless the new one is stored.
        with transaction.atomic():
            self._base_queryset().filter(lead_id=summary.lead_id).delete()

            return DjangoLeadSummaryModel.objects.create(
                id=summary.id,
                # Always the repository's own company, never the entity's.
                company_id=self._company_id,
                lead_id=summary.lead_id,
                headline=summary.headline,
                key_points=list(summary.key_points),
                next_steps=list(summary.next_steps),
                model_name=summary.model_name,
                timeline_events_used=summary.timeline_events_used,
                calls_used=summary.calls_used,
                generated_at=summary.generated_at,
            )

    def delete_by_lead_id(self, lead_id: UUID) -> int:
        deleted, _ = self._base_queryset().filter(lead_id=lead_id).delete()
        return deleted

    def _to_domain(self, model: DjangoLeadSummaryModel) -> LeadSummary:
        return LeadSummary(
            id=model.id,
            lead_id=model.lead_id,
            headline=model.headline,
            key_points=list(model.key_points or []),
            next_steps=list(model.next_steps or []),
            model_name=model.model_name,
            timeline_events_used=model.timeline_events_used,
            calls_used=model.calls_used,
            generated_at=model.generated_at,
        )
