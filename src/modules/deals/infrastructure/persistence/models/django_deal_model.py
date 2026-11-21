import uuid

from django.conf import settings
from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.db.models.functions import Upper
from django.db.models.indexes import OpClass

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.deals.domain.enums.deal_stage import (
    DEFAULT_PROBABILITY,
    DealStage,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)


class DjangoDealModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=255,
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    expected_close_date = models.DateField(
        blank=True,
        null=True,
    )

    stage = models.CharField(
        max_length=100,
        choices=[
            (stage.value, stage.value)
            for stage in DealStage
        ],
        default=DealStage.NEW.value,
    )

    probability = models.PositiveSmallIntegerField(
        default=DEFAULT_PROBABILITY[DealStage.NEW],
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_deals",
    )

    account = models.ForeignKey(
        DjangoAccountModel,
        on_delete=models.PROTECT,
        related_name="deals",
        blank=True,
        null=True,
    )

    contact = models.ForeignKey(
        DjangoContactModel,
        on_delete=models.PROTECT,
        related_name="deals",
        blank=True,
        null=True,
    )

    source_lead = models.ForeignKey(
        DjangoLeadModel,
        on_delete=models.SET_NULL,
        related_name="deals",
        blank=True,
        null=True,
    )

    lead_source = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    lost_reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    closed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_deals",
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
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    class Meta:
        db_table = "deals"
        indexes = [
            models.Index(
                fields=["company", "is_deleted", "stage"],
                name="deals_company_stage_idx",
            ),
            models.Index(
                fields=["company", "is_deleted", "expected_close_date"],
                name="deals_company_close_idx",
            ),
            # List sort / filters (see migration 0002_deal_list_indexes and
            # 0003_deal_relation_indexes).
            models.Index(
                fields=["company", "is_deleted", "created_at"],
                name="deals_co_created_idx",
            ),
            models.Index(
                fields=["company", "is_deleted", "owner"],
                name="deals_co_owner_idx",
            ),
            models.Index(
                fields=["company", "is_deleted", "account"],
                name="deals_co_account_idx",
            ),
            models.Index(
                fields=["company", "is_deleted", "contact"],
                name="deals_co_contact_idx",
            ),
            # Search / "contains" filters on name (UPPER(...) is what the
            # case-insensitive lookups query; see migration 0004_deal_search_trigram_index).
            GinIndex(
                OpClass(Upper("name"), name="gin_trgm_ops"),
                name="deals_name_trgm_idx",
            ),
        ]

    def __str__(self):
        return self.name
