from uuid import UUID

from django.db import IntegrityError, transaction

from src.modules.calls.application.interfaces.call_recording_transcript_repository import (
    CallRecordingTranscriptRepository,
)
from src.modules.calls.domain.entities.call_recording_transcript import (
    CallRecordingTranscript,
    TranscriptSegment,
)
from src.modules.calls.domain.enums.transcription_status import TranscriptionStatus

from .models import DjangoCallRecordingTranscriptModel


class DjangoCallRecordingTranscriptRepository(CallRecordingTranscriptRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoCallRecordingTranscriptModel.objects.filter(
            company_id=self._company_id
        )

    def save(self, transcript: CallRecordingTranscript) -> CallRecordingTranscript:
        try:
            # Savepoint: a unique-violation must not poison an outer transaction.
            with transaction.atomic():
                model, _ = self._base_queryset().update_or_create(
                    id=transcript.id,
                    defaults=self._to_defaults(transcript),
                )
        except IntegrityError:
            # Lost a race with another request for the same recording.
            model = self._base_queryset().filter(
                recording_id=transcript.recording_id
            ).first()

            if model is None:
                raise

        return self._to_domain(model)

    def _to_defaults(self, transcript: CallRecordingTranscript) -> dict:
        return {
            "company_id": self._company_id,
            "recording_id": transcript.recording_id,
            "call_id": transcript.call_id,
            "status": transcript.status.value,
            "transcript_text": transcript.transcript_text,
            "segments": [segment.to_dict() for segment in transcript.segments],
            "summary": transcript.summary,
            "key_points": list(transcript.key_points),
            "action_items": list(transcript.action_items),
            "language": transcript.language,
            "model_name": transcript.model_name,
            "error_message": transcript.error_message,
            "requested_by_id": transcript.requested_by_id,
            "started_at": transcript.started_at,
            "completed_at": transcript.completed_at,
        }

    def get_by_recording_id(self, recording_id: UUID) -> CallRecordingTranscript | None:
        try:
            model = self._base_queryset().get(recording_id=recording_id)
        except DjangoCallRecordingTranscriptModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_completed_for_calls(
        self,
        call_ids: list[UUID],
    ) -> list[CallRecordingTranscript]:
        ids = list(call_ids)
        if not ids:
            return []

        models = self._base_queryset().filter(
            call_id__in=ids,
            call__is_deleted=False,
            status=TranscriptionStatus.COMPLETED.value,
        ).order_by("-completed_at", "-id")

        return [self._to_domain(model) for model in models]

    @staticmethod
    def _to_domain(model: DjangoCallRecordingTranscriptModel) -> CallRecordingTranscript:
        return CallRecordingTranscript(
            id=model.id,
            recording_id=model.recording_id,
            call_id=model.call_id,
            status=TranscriptionStatus(model.status),
            requested_by_id=model.requested_by_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            transcript_text=model.transcript_text,
            segments=[TranscriptSegment.from_dict(item) for item in (model.segments or [])],
            summary=model.summary,
            key_points=list(model.key_points or []),
            action_items=list(model.action_items or []),
            language=model.language,
            model_name=model.model_name,
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
        )
