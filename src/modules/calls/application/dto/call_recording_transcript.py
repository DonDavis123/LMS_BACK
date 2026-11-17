from dataclasses import dataclass, field
from uuid import UUID

from src.modules.calls.domain.entities.call_recording_transcript import (
    CallRecordingTranscript,
    TranscriptSegment,
)


@dataclass(frozen=True)
class TranscriptionResult:
    """What a transcription service returns for one audio file."""

    transcript_text: str
    summary: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    language: str | None = None
    model_name: str | None = None


@dataclass(frozen=True)
class RequestTranscriptionDTO:
    call_id: UUID
    recording_id: UUID
    requested_by_id: UUID | None = None
    # Run again even when a finished transcript exists (costs another API call).
    regenerate: bool = False


@dataclass(frozen=True)
class RecordingTranscriptDTO:
    """Read model returned by the get / request use cases.

    ``transcript`` is ``None`` when nobody has asked to transcribe the
    recording yet.
    """

    recording_id: UUID
    call_id: UUID
    transcript: CallRecordingTranscript | None = None
