import uuid

from django.db import models

from .django_contact_model import DjangoContactModel


class DjangoContactSummaryModel(models.Model):
    """The current AI summary of one contact (at most one row per contact)."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Deleting the contact (hard delete) deletes its summary with it.
    contact = models.OneToOneField(
        DjangoContactModel,
        on_delete=models.CASCADE,
        related_name="+",
    )

    headline = models.TextField()

    key_points = models.JSONField(default=list)

    next_steps = models.JSONField(default=list)

    model_name = models.CharField(max_length=100, blank=True, null=True)

    timeline_events_used = models.PositiveIntegerField(default=0)

    calls_used = models.PositiveIntegerField(default=0)

    generated_at = models.DateTimeField()

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    class Meta:
        db_table = "contact_summaries"

    def __str__(self):
        return f"Summary of contact {self.contact_id}"
