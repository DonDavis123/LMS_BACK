from enum import Enum


class TranscriptionStatus(str, Enum):
    """Where the transcription of one call recording stands."""

    PENDING = "PENDING"        # queued, not picked up yet
    PROCESSING = "PROCESSING"  # the transcription service is working on it
    COMPLETED = "COMPLETED"    # transcript and summary are available
    FAILED = "FAILED"          # gave up; ``error_message`` says why

    # Never stored. Returned by the API for a recording nobody asked to
    # transcribe, so a client can poll one URL without special-casing 404.
    NOT_REQUESTED = "NOT_REQUESTED"

    @property
    def is_active(self) -> bool:
        return self in (TranscriptionStatus.PENDING, TranscriptionStatus.PROCESSING)
