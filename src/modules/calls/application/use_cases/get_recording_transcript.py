from uuid import UUID

from src.modules.calls.application.dto.call_recording_transcript import (
    RecordingTranscriptDTO,
)
from src.modules.calls.application.interfaces.call_recording_repository import (
    CallRecordingRepository,
)
from src.modules.calls.application.interfaces.call_recording_transcript_repository import (
    CallRecordingTranscriptRepository,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository


class GetRecordingTranscriptUseCase:

    def __init__(
        self,
        call_repository: CallRepository,
        recording_repository: CallRecordingRepository,
        transcript_repository: CallRecordingTranscriptRepository,
    ):
        self.call_repository = call_repository
        self.recording_repository = recording_repository
        self.transcript_repository = transcript_repository

    def execute(self, call_id: UUID, recording_id: UUID) -> RecordingTranscriptDTO:
        if self.call_repository.get_by_id(call_id) is None:
            raise ValueError("Call not found.")

        recording = self.recording_repository.get_by_id(recording_id, call_id)

        if recording is None:
            raise ValueError("Recording not found.")

        return RecordingTranscriptDTO(
            recording_id=recording.id,
            call_id=recording.call_id,
            transcript=self.transcript_repository.get_by_recording_id(recording.id),
        )
