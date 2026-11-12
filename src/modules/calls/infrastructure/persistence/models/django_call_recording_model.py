import uuid

from django.conf import settings
from django.db import models

from .django_call_model import DjangoCallModel


class DjangoCallRecordingModel(models.Model):
    """Metadata of a voice recording; the audio itself is in file storage."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Recordings go when their call is permanently deleted (for example when
    # a retired user's calls are cleaned up). Soft-deleted calls keep them.
    call = models.ForeignKey(
        DjangoCallModel,
        on_delete=models.CASCADE,
        related_name="recordings",
    )

    # A recording must outlive the account of the person who uploaded it.
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )

    file_name = models.CharField(max_length=255)

    content_type = models.CharField(max_length=100)

    size_bytes = models.PositiveBigIntegerField()

    duration_seconds = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    storage_key = models.CharField(
        max_length=500,
        unique=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    class Meta:
        db_table = "call_recordings"
        indexes = [
            models.Index(
                fields=["company", "call", "-created_at"],
                name="call_rec_co_call_created_idx",
            ),
        ]

    def __str__(self):
        return f"Recording {self.file_name} of call {self.call_id}"
