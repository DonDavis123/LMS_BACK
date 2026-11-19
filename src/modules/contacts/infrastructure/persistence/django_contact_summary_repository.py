from uuid import UUID

from django.db import IntegrityError, transaction

from src.modules.contacts.application.interfaces.contact_summary_repository import (
    ContactSummaryRepository,
)
from src.modules.contacts.domain.entities.contact_summary import ContactSummary

from .django_contact_summary_model import DjangoContactSummaryModel


class DjangoContactSummaryRepository(ContactSummaryRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoContactSummaryModel.objects.filter(company_id=self._company_id)

    def get_by_contact_id(self, contact_id: UUID) -> ContactSummary | None:
        model = self._base_queryset().filter(contact_id=contact_id).first()

        if model is None:
            return None

        return self._to_domain(model)

    def replace_for_contact(self, summary: ContactSummary) -> ContactSummary:
        try:
            model = self._delete_then_create(summary)
        except IntegrityError:
            # Another refresh of the same contact committed between our delete
            # and our insert (one summary per contact is enforced by the
            # database). Run again: this time the winner's row is deleted
            # and ours is stored, so the latest request wins.
            model = self._delete_then_create(summary)

        return self._to_domain(model)

    def _delete_then_create(self, summary: ContactSummary) -> DjangoContactSummaryModel:
        # One transaction (a savepoint when an outer one is open): the old
        # summary is never lost unless the new one is stored.
        with transaction.atomic():
            self._base_queryset().filter(contact_id=summary.contact_id).delete()

            return DjangoContactSummaryModel.objects.create(
                id=summary.id,
                # Always the repository's own company, never the entity's.
                company_id=self._company_id,
                contact_id=summary.contact_id,
                headline=summary.headline,
                key_points=list(summary.key_points),
                next_steps=list(summary.next_steps),
                model_name=summary.model_name,
                timeline_events_used=summary.timeline_events_used,
                calls_used=summary.calls_used,
                generated_at=summary.generated_at,
            )

    def delete_by_contact_id(self, contact_id: UUID) -> int:
        deleted, _ = self._base_queryset().filter(contact_id=contact_id).delete()
        return deleted

    def _to_domain(self, model: DjangoContactSummaryModel) -> ContactSummary:
        return ContactSummary(
            id=model.id,
            contact_id=model.contact_id,
            headline=model.headline,
            key_points=list(model.key_points or []),
            next_steps=list(model.next_steps or []),
            model_name=model.model_name,
            timeline_events_used=model.timeline_events_used,
            calls_used=model.calls_used,
            generated_at=model.generated_at,
        )
