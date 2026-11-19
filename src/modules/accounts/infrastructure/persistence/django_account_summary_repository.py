from uuid import UUID

from django.db import IntegrityError, transaction

from src.modules.accounts.application.interfaces.account_summary_repository import (
    AccountSummaryRepository,
)
from src.modules.accounts.domain.entities.account_summary import AccountSummary

from .django_account_summary_model import DjangoAccountSummaryModel


class DjangoAccountSummaryRepository(AccountSummaryRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoAccountSummaryModel.objects.filter(company_id=self._company_id)

    def get_by_account_id(self, account_id: UUID) -> AccountSummary | None:
        model = self._base_queryset().filter(account_id=account_id).first()

        if model is None:
            return None

        return self._to_domain(model)

    def replace_for_account(self, summary: AccountSummary) -> AccountSummary:
        try:
            model = self._delete_then_create(summary)
        except IntegrityError:
            # Another refresh of the same account committed between our delete
            # and our insert (one summary per account is enforced by the
            # database). Run again: this time the winner's row is deleted
            # and ours is stored, so the latest request wins.
            model = self._delete_then_create(summary)

        return self._to_domain(model)

    def _delete_then_create(self, summary: AccountSummary) -> DjangoAccountSummaryModel:
        # One transaction (a savepoint when an outer one is open): the old
        # summary is never lost unless the new one is stored.
        with transaction.atomic():
            self._base_queryset().filter(account_id=summary.account_id).delete()

            return DjangoAccountSummaryModel.objects.create(
                id=summary.id,
                # Always the repository's own company, never the entity's.
                company_id=self._company_id,
                account_id=summary.account_id,
                headline=summary.headline,
                key_points=list(summary.key_points),
                next_steps=list(summary.next_steps),
                model_name=summary.model_name,
                timeline_events_used=summary.timeline_events_used,
                calls_used=summary.calls_used,
                contacts_used=summary.contacts_used,
                generated_at=summary.generated_at,
            )

    def delete_by_account_id(self, account_id: UUID) -> int:
        deleted, _ = self._base_queryset().filter(account_id=account_id).delete()
        return deleted

    def _to_domain(self, model: DjangoAccountSummaryModel) -> AccountSummary:
        return AccountSummary(
            id=model.id,
            account_id=model.account_id,
            headline=model.headline,
            key_points=list(model.key_points or []),
            next_steps=list(model.next_steps or []),
            model_name=model.model_name,
            timeline_events_used=model.timeline_events_used,
            calls_used=model.calls_used,
            contacts_used=model.contacts_used,
            generated_at=model.generated_at,
        )
