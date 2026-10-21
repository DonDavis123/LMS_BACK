import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.calls.domain.enums.call_entry_method import CallEntryMethod
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_type import CallType
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)


class DjangoCallModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    lead = models.ForeignKey(
        DjangoLeadModel,
        on_delete=models.PROTECT,
        related_name="calls",
        blank=True,
        null=True,
    )

    contact = models.ForeignKey(
        DjangoContactModel,
        on_delete=models.PROTECT,
        related_name="calls",
        blank=True,
        null=True,
    )

    account = models.ForeignKey(
        DjangoAccountModel,
        on_delete=models.PROTECT,
        related_name="calls",
        blank=True,
        null=True,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_calls",
    )

    call_type = models.CharField(
        max_length=100,
        choices=[
            (call_type.value, call_type.value)
            for call_type in CallType
        ],
        default=CallType.OUTBOUND,
    )

    outcome = models.CharField(
        max_length=100,
        choices=[
            (outcome.value, outcome.value)
            for outcome in CallOutcome
        ],
    )

    entry_method = models.CharField(
        max_length=100,
        choices=[
            (method.value, method.value)
            for method in CallEntryMethod
        ],
        default=CallEntryMethod.MANUAL,
    )

    call_start_time = models.DateTimeField()

    duration_seconds = models.PositiveIntegerField(
        default=0,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_calls",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    is_deleted = models.BooleanField(
        default=False,
    )

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    class Meta:
        db_table = "calls"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(lead__isnull=False, contact__isnull=True)
                    | Q(lead__isnull=True, contact__isnull=False)
                ),
                name="call_exactly_one_of_lead_contact",
            ),
            models.CheckConstraint(
                condition=Q(account__isnull=True) | Q(contact__isnull=False),
                name="call_account_only_with_contact",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "lead", "-call_start_time"],
                name="calls_co_lead_start_idx",
            ),
            models.Index(
                fields=["company", "contact", "-call_start_time"],
                name="calls_co_contact_start_idx",
            ),
        ]

    def __str__(self):
        return f"{self.call_type} call ({self.outcome})"
