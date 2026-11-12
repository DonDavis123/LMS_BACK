from dataclasses import dataclass
from typing import BinaryIO
from uuid import UUID

from src.modules.calls.domain.entities.call_recording import CallRecording


@dataclass(frozen=True)
class UploadCallRecordingDTO:
    call_id: UUID
    uploaded_by_id: UUID
    file_name: str | None
    content_type: str | None
    size_bytes: int
    content: BinaryIO
    duration_seconds: int | None = None


@dataclass(frozen=True)
class GetCallRecordingDTO:
    """Read model: a recording plus the display name of who uploaded it."""

    recording: CallRecording
    uploaded_by_name: str | None = None


@dataclass(frozen=True)
class CallRecordingFileDTO:
    """A recording together with its opened audio stream."""

    recording: CallRecording
    content: BinaryIO
