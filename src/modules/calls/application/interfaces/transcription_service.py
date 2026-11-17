from abc import ABC, abstractmethod

from src.modules.calls.application.dto.call_recording_transcript import (
    TranscriptionResult,
)


class TranscriptionError(Exception):
    """The transcription service failed for this recording.

    ``user_message`` is safe to show to the end user (no keys, no raw
    provider payloads); the technical detail goes to the server log.
    """

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class TranscriptionUnavailableError(Exception):
    """Transcription is not set up on this server (for example no API key)."""


class TranscriptionService(ABC):
    """Turns call audio into a transcript and a summary."""

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def transcribe(
        self,
        *,
        audio: bytes,
        content_type: str,
        file_name: str,
    ) -> TranscriptionResult:
        """Raises ``TranscriptionError`` when the audio could not be processed."""
        pass
