import uuid

from django.conf import settings
from django.db import models

from .django_call_model import DjangoCallModel
from .django_call_recording_model import DjangoCallRecordingModel


class DjangoCallRecordingTranscriptModel(models.Model):
    """Transcript and summary of one recording (at most one per recording)."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Deleting the recording (or its call) deletes its transcript with it.
    recording = models.OneToOneField(
        DjangoCallRecordingModel,
        on_delete=models.CASCADE,
        related_name="transcript",
    )

    call = models.ForeignKey(
        DjangoCallModel,
        on_delete=models.CASCADE,
        related_name="+",
    )

    status = models.CharField(max_length=20)

    transcript_text = models.TextField(blank=True, null=True)

    # [{"speaker": ..., "timestamp": ..., "text": ...}, ...]
    segments = models.JSONField(default=list)

    summary = models.TextField(blank=True, null=True)

    key_points = models.JSONField(default=list)

    action_items = models.JSONField(default=list)

    language = models.CharField(max_length=50, blank=True, null=True)

    model_name = models.CharField(max_length=100, blank=True, null=True)

    error_message = models.CharField(max_length=500, blank=True, null=True)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )

    started_at = models.DateTimeField(blank=True, null=True)

    completed_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    class Meta:
        db_table = "call_recording_transcripts"

    def __str__(self):
        return f"Transcript of recording {self.recording_id} ({self.status})"
