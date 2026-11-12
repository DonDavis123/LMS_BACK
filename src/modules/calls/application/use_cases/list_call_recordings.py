from uuid import UUID

from src.modules.calls.application.dto.call_recording import GetCallRecordingDTO
from src.modules.calls.application.interfaces.call_recording_repository import (
    CallRecordingRepository,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository


class ListCallRecordingsUseCase:

    def __init__(
        self,
        call_repository: CallRepository,
        recording_repository: CallRecordingRepository,
    ):
        self.call_repository = call_repository
        self.recording_repository = recording_repository

    def execute(self, call_id: UUID) -> list[GetCallRecordingDTO] | None:
        """The call's recordings, newest first; ``None`` when the call is unknown."""
        if self.call_repository.get_by_id(call_id) is None:
            return None

        return self.recording_repository.list_by_call_id(call_id)
