import uuid

from django.db import models
from django.db.models.functions import Lower


class DjangoPicklistOptionModel(models.Model):
    """One selectable option of a customisable dropdown, per company."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        on_delete=models.CASCADE,
        related_name="+",
    )

    # Which screen / dropdown this belongs to, e.g. "leads" / "lead_source".
    module = models.CharField(max_length=50)
    field = models.CharField(max_length=50)

    value = models.CharField(max_length=150)

    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "picklist_options"
        ordering = ["sort_order", "value"]
        constraints = [
            # One option per text per dropdown, ignoring upper/lower case.
            models.UniqueConstraint(
                "company",
                "module",
                "field",
                Lower("value"),
                name="uniq_picklist_option_value",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "module", "field", "sort_order"],
                name="picklist_lookup_idx",
            ),
        ]

    def __str__(self):
        return f"{self.module}.{self.field}: {self.value}"
