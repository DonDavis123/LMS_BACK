from uuid import UUID

from src.modules.calls.application.dto.call_recording import CallRecordingFileDTO
from src.modules.calls.application.interfaces.call_recording_repository import (
    CallRecordingRepository,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.calls.application.interfaces.recording_storage import (
    RecordingStorage,
)


class GetCallRecordingFileUseCase:
    FILE_MISSING_MESSAGE = "The recording file is no longer available."

    def __init__(
        self,
        call_repository: CallRepository,
        recording_repository: CallRecordingRepository,
        storage: RecordingStorage,
    ):
        self.call_repository = call_repository
        self.recording_repository = recording_repository
        self.storage = storage

    def execute(self, call_id: UUID, recording_id: UUID) -> CallRecordingFileDTO:
        if self.call_repository.get_by_id(call_id) is None:
            raise ValueError("Call not found.")

        recording = self.recording_repository.get_by_id(recording_id, call_id)

        if recording is None:
            raise ValueError("Recording not found.")

        try:
            content = self.storage.open(recording.storage_key)
        except FileNotFoundError:
            raise ValueError(self.FILE_MISSING_MESSAGE)

        return CallRecordingFileDTO(recording=recording, content=content)
