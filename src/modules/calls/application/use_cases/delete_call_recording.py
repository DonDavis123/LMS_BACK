import logging
from uuid import UUID

from src.modules.calls.application.interfaces.call_recording_repository import (
    CallRecordingRepository,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.calls.application.interfaces.recording_storage import (
    RecordingStorage,
)
from src.modules.calls.application.use_cases.upload_call_recording import (
    call_targets,
)
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.timeline.application.interfaces.timeline_recorder import (
    TimelineRecorder,
)

logger = logging.getLogger(__name__)


class DeleteCallRecordingUseCase:

    def __init__(
        self,
        call_repository: CallRepository,
        recording_repository: CallRecordingRepository,
        storage: RecordingStorage,
        timeline_recorder: TimelineRecorder,
        transaction_manager: TransactionManager,
    ):
        self.call_repository = call_repository
        self.recording_repository = recording_repository
        self.storage = storage
        self.timeline_recorder = timeline_recorder
        self.transaction_manager = transaction_manager

    def execute(self, call_id: UUID, recording_id: UUID, current_user_id=None) -> None:
        call = self.call_repository.get_by_id(call_id)

        if call is None:
            raise ValueError("Call not found.")

        recording = self.recording_repository.get_by_id(recording_id, call_id)

        if recording is None:
            raise ValueError("Recording not found.")

        def deletion() -> None:
            self.recording_repository.delete(recording.id)

            self.timeline_recorder.record(
                event_type="CALL_RECORDING_DELETED",
                actor_id=current_user_id or call.owner_id,
                message=f'Call recording deleted ("{recording.file_name}").',
                metadata={
                    "call_id": str(call.id),
                    "recording_id": str(recording.id),
                    "file_name": recording.file_name,
                },
                targets=call_targets(call),
            )

        self.transaction_manager.execute(deletion)

        # Only after the row is gone for good: a failed transaction must
        # never leave a row pointing at deleted audio.
        try:
            self.storage.delete(recording.storage_key)
        except Exception:
            logger.exception(
                "Could not remove the audio of call recording %s", recording.id
            )
