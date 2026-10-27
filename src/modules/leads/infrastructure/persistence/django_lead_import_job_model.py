import uuid

from django.conf import settings
from django.db import models


class LeadImportJob(models.Model):

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        UNDONE = "undone", "Undone"
        PARTLY_UNDONE = "partly_undone", "Partly undone"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Tenant ownership: same convention as the lead model.
    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    file_name = models.CharField(
        max_length=255,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )

    # File layout

    header_row = models.PositiveIntegerField(
        default=1,
    )

    sheet_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    # Original file headers, in order.
    headers = models.JSONField(
        default=list,
        blank=True,
    )

    # File column -> CRM field key.
    mapping = models.JSONField(
        default=dict,
        blank=True,
    )

    # duplicate_action, owner_plan, round_robin_cursor, change_owner_on_update
    options = models.JSONField(
        default=dict,
        blank=True,
    )

    # Stored file rows until purged:
    # [{row_number, original: {header: value}, cleaned: {field: value},
    #   in_file_duplicate_of: int | None}]
    rows = models.JSONField(
        null=True,
        blank=True,
    )

    # Counters

    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)

    # [{row_number, column, field, value, code, message, how_to_fix,
    #   kind: error | skipped_duplicate | skipped_converted}]
    problems = models.JSONField(
        default=list,
        blank=True,
    )

    # lead_id -> previous field values, used by undo.
    update_snapshots = models.JSONField(
        default=dict,
        blank=True,
    )

    # Safe, user-facing text only. Never a raw exception.
    failure_message = models.TextField(
        blank=True,
        default="",
    )

    # Timestamps

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_activity_at = models.DateTimeField(
        auto_now_add=True,
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    undone_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    undone_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    rows_purged_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "lead_import_jobs"
        indexes = [
            models.Index(
                fields=["company", "-created_at"],
                name="lead_import_company_idx",
            ),
            models.Index(
                fields=["status", "last_activity_at"],
                name="lead_import_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.file_name} ({self.status})"
