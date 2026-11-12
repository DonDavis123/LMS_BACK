import uuid

from django.conf import settings
from django.db import models

from .django_account_model import DjangoAccountModel


class DjangoAccountDocumentModel(models.Model):
    """A named link (name + URL) to a document of an account."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    account = models.ForeignKey(
        DjangoAccountModel,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    name = models.CharField(max_length=255)
    url = models.URLField(max_length=2000)

    # Audit fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    created_at = models.DateTimeField()

    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    updated_at = models.DateTimeField()

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    class Meta:
        db_table = "account_documents"
        indexes = [
            models.Index(
                fields=["company", "account", "created_at"],
                name="acc_doc_co_acc_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.account_id})"
