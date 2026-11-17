from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.calls.domain.entities.call_recording_transcript import (
    CallRecordingTranscript,
)


class CallRecordingTranscriptRepository(ABC):

    @abstractmethod
    def save(self, transcript: CallRecordingTranscript) -> CallRecordingTranscript:
        """Insert or update.

        A recording has at most one transcript. When a concurrent request
        already created one under another id, that stored transcript is
        returned unchanged instead of raising.
        """
        pass

    @abstractmethod
    def get_by_recording_id(self, recording_id: UUID) -> CallRecordingTranscript | None:
        pass
