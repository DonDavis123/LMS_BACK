from uuid import UUID

from django.db.models import Sum

from src.modules.calls.application.dto.call_recording import GetCallRecordingDTO
from src.modules.calls.application.interfaces.call_recording_repository import (
    CallRecordingRepository,
)
from src.modules.calls.domain.entities.call_recording import CallRecording

from .models import DjangoCallRecordingModel


class DjangoCallRecordingRepository(CallRecordingRepository):

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoCallRecordingModel.objects.filter(company_id=self._company_id)

    def save(self, recording: CallRecording) -> CallRecording:
        model, _ = self._base_queryset().update_or_create(
            id=recording.id,
            defaults={
                "company_id": self._company_id,
                "call_id": recording.call_id,
                "uploaded_by_id": recording.uploaded_by_id,
                "file_name": recording.file_name,
                "content_type": recording.content_type,
                "size_bytes": recording.size_bytes,
                "duration_seconds": recording.duration_seconds,
                "storage_key": recording.storage_key,
            },
        )

        return self._to_domain(model)

    def get_by_id(
        self,
        recording_id: UUID,
        call_id: UUID,
    ) -> CallRecording | None:
        try:
            model = self._base_queryset().get(id=recording_id, call_id=call_id)
        except DjangoCallRecordingModel.DoesNotExist:
            return None

        return self._to_domain(model)

    def get_with_relations(self, recording_id: UUID) -> GetCallRecordingDTO | None:
        try:
            model = (
                self._base_queryset()
                .select_related("uploaded_by")
                .get(id=recording_id)
            )
        except DjangoCallRecordingModel.DoesNotExist:
            return None

        return self._to_dto(model)

    def list_by_call_id(self, call_id: UUID) -> list[GetCallRecordingDTO]:
        models = (
            self._base_queryset()
            .filter(call_id=call_id)
            .select_related("uploaded_by")
            .order_by("-created_at", "-id")
        )

        return [self._to_dto(model) for model in models]

    def count_by_call_id(self, call_id: UUID) -> int:
        return self._base_queryset().filter(call_id=call_id).count()

    def total_size_bytes(self) -> int:
        # Not filtered by company on purpose: the storage bucket is shared.
        total = DjangoCallRecordingModel.objects.aggregate(total=Sum("size_bytes"))
        return total["total"] or 0

    def delete(self, recording_id: UUID) -> None:
        self._base_queryset().filter(id=recording_id).delete()

    @staticmethod
    def _to_dto(model: DjangoCallRecordingModel) -> GetCallRecordingDTO:
        uploader = model.uploaded_by

        return GetCallRecordingDTO(
            recording=DjangoCallRecordingRepository._to_domain(model),
            uploaded_by_name=uploader.name if uploader is not None else None,
        )

    @staticmethod
    def _to_domain(model: DjangoCallRecordingModel) -> CallRecording:
        return CallRecording(
            id=model.id,
            call_id=model.call_id,
            uploaded_by_id=model.uploaded_by_id,
            file_name=model.file_name,
            content_type=model.content_type,
            size_bytes=model.size_bytes,
            duration_seconds=model.duration_seconds,
            storage_key=model.storage_key,
            created_at=model.created_at,
        )
