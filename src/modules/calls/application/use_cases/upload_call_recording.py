from src.modules.calls.application.dto.call_recording import (
    GetCallRecordingDTO,
    UploadCallRecordingDTO,
)
from src.modules.calls.application.interfaces.call_recording_repository import (
    CallRecordingRepository,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.calls.application.interfaces.recording_storage import (
    RecordingStorage,
)
from src.modules.calls.domain.entities.call_recording import CallRecording
from src.modules.calls.domain.enums.call_status import CallStatus
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.timeline.application.interfaces.timeline_recorder import (
    TimelineRecorder,
)

DEFAULT_MAX_SIZE_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_PER_CALL = 10


def format_size(size_bytes: int) -> str:
    """``1.4 MB`` / ``312 KB`` for timeline messages."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{max(1, round(size_bytes / 1024))} KB"


def call_targets(call) -> list[tuple[str, object]]:
    """Timeline targets of a call: itself plus its lead / contact / account."""
    targets = [("CALL", call.id)]

    if call.lead_id:
        targets.append(("LEAD", call.lead_id))
    if call.contact_id:
        targets.append(("CONTACT", call.contact_id))
    if call.account_id:
        targets.append(("ACCOUNT", call.account_id))

    return targets


class UploadCallRecordingUseCase:
    NOT_COMPLETED_MESSAGE = "Recordings can only be added to a completed call."
    STORAGE_FULL_MESSAGE = (
        "Recording storage is full. Delete old recordings or ask your "
        "administrator to free up space."
    )

    def __init__(
        self,
        call_repository: CallRepository,
        recording_repository: CallRecordingRepository,
        storage: RecordingStorage,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
        max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
        max_per_call: int = DEFAULT_MAX_PER_CALL,
        max_total_bytes: int | None = None,
    ):
        self.call_repository = call_repository
        self.recording_repository = recording_repository
        self.storage = storage
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager
        self.max_size_bytes = max_size_bytes
        self.max_per_call = max_per_call
        # ``None`` means the storage has no overall size limit.
        self.max_total_bytes = max_total_bytes

    def execute(self, data: UploadCallRecordingDTO) -> GetCallRecordingDTO:
        call = self.call_repository.get_by_id(data.call_id)

        if call is None:
            raise ValueError("Call not found.")

        if call.status != CallStatus.COMPLETED:
            raise ValueError(self.NOT_COMPLETED_MESSAGE)

        if self.recording_repository.count_by_call_id(call.id) >= self.max_per_call:
            raise ValueError(
                f"A call can have at most {self.max_per_call} recordings. "
                "Delete one before adding another."
            )

        # Validates the file details before a single byte is stored.
        recording = CallRecording.create(
            call_id=call.id,
            uploaded_by_id=data.uploaded_by_id,
            file_name=data.file_name,
            content_type=data.content_type,
            size_bytes=data.size_bytes,
            max_size_bytes=self.max_size_bytes,
            duration_seconds=data.duration_seconds,
        )

        if self.max_total_bytes is not None and (
            self.recording_repository.total_size_bytes() + recording.size_bytes
            > self.max_total_bytes
        ):
            raise ValueError(self.STORAGE_FULL_MESSAGE)

        recording.storage_key = self.storage.store(
            call_id=call.id,
            recording_id=recording.id,
            extension=recording.extension,
            content=data.content,
        )

        def creation() -> GetCallRecordingDTO:
            saved = self.recording_repository.save(recording)

            self.timeline_recorder.record(
                event_type="CALL_RECORDING_ADDED",
                actor_id=data.uploaded_by_id,
                message=(
                    f'Call recording added ("{saved.file_name}", '
                    f"{format_size(saved.size_bytes)})."
                ),
                metadata={
                    "call_id": str(call.id),
                    "recording_id": str(saved.id),
                    "file_name": saved.file_name,
                    "size_bytes": saved.size_bytes,
                },
                targets=call_targets(call),
            )

            return self.recording_repository.get_with_relations(saved.id) or (
                GetCallRecordingDTO(recording=saved)
            )

        try:
            return self.transaction_manager.execute(creation)
        except Exception:
            # Never leave audio behind that no row points to.
            self._discard_stored_audio(recording.storage_key)
            raise

    def _discard_stored_audio(self, storage_key: str) -> None:
        try:
            self.storage.delete(storage_key)
        except Exception:  # pragma: no cover - best effort clean-up
            pass
