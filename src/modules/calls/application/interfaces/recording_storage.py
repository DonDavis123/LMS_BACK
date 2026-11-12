from abc import ABC, abstractmethod
from typing import BinaryIO
from uuid import UUID


class RecordingStorage(ABC):
    """Where the audio bytes of call recordings are kept."""

    @abstractmethod
    def store(
        self,
        *,
        call_id: UUID,
        recording_id: UUID,
        extension: str,
        content: BinaryIO,
    ) -> str:
        """Save the audio and return its storage key."""
        pass

    @abstractmethod
    def open(self, storage_key: str) -> BinaryIO:
        """Open the stored audio. Raises ``FileNotFoundError`` when missing."""
        pass

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Remove the stored audio. A missing file is not an error."""
        pass
