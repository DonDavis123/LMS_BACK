import uuid

from django.db import models

from .django_account_model import DjangoAccountModel


class DjangoAccountSummaryModel(models.Model):
    """The current AI summary of one account (at most one row per account)."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Deleting the account (hard delete) deletes its summary with it.
    account = models.OneToOneField(
        DjangoAccountModel,
        on_delete=models.CASCADE,
        related_name="+",
    )

    headline = models.TextField()

    key_points = models.JSONField(default=list)

    next_steps = models.JSONField(default=list)

    model_name = models.CharField(max_length=100, blank=True, null=True)

    timeline_events_used = models.PositiveIntegerField(default=0)

    calls_used = models.PositiveIntegerField(default=0)

    contacts_used = models.PositiveIntegerField(default=0)

    generated_at = models.DateTimeField()

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    class Meta:
        db_table = "account_summaries"

    def __str__(self):
        return f"Summary of account {self.account_id}"
