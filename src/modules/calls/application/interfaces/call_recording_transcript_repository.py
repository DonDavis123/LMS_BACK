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

    def get_completed_for_calls(
        self,
        call_ids: list[UUID],
    ) -> list[CallRecordingTranscript]:
        """COMPLETED transcripts (with a summary) of the given calls, newest first.

        One query for all calls. Not abstract so existing in-memory test
        doubles keep working.
        """
        raise NotImplementedError
