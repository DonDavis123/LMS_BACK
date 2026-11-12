from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.calls.application.dto.call_recording import GetCallRecordingDTO
from src.modules.calls.domain.entities.call_recording import CallRecording


class CallRecordingRepository(ABC):

    @abstractmethod
    def save(self, recording: CallRecording) -> CallRecording:
        pass

    @abstractmethod
    def get_by_id(
        self,
        recording_id: UUID,
        call_id: UUID,
    ) -> CallRecording | None:
        """The recording, only when it belongs to ``call_id``."""
        pass

    @abstractmethod
    def get_with_relations(self, recording_id: UUID) -> GetCallRecordingDTO | None:
        pass

    @abstractmethod
    def list_by_call_id(self, call_id: UUID) -> list[GetCallRecordingDTO]:
        """Recordings of one call, newest first."""
        pass

    @abstractmethod
    def count_by_call_id(self, call_id: UUID) -> int:
        pass

    @abstractmethod
    def total_size_bytes(self) -> int:
        """Bytes of audio kept for recordings of ALL companies.

        Deliberately not tenant scoped: every company shares one storage
        bucket, so its size limit has to be checked against the whole bucket.
        Only a number is returned, never another company's data.
        """
        pass

    @abstractmethod
    def delete(self, recording_id: UUID) -> None:
        """Permanently remove the recording row."""
        pass
