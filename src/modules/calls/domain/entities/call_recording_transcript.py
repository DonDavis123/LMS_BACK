from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.modules.calls.domain.enums.transcription_status import TranscriptionStatus

MAX_ERROR_MESSAGE_LENGTH = 500


@dataclass(frozen=True)
class TranscriptSegment:
    """One spoken turn of the conversation."""

    speaker: str
    text: str
    timestamp: str | None = None  # "MM:SS" or "H:MM:SS" from the start of the audio

    def to_dict(self) -> dict:
        return {"speaker": self.speaker, "timestamp": self.timestamp, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptSegment":
        return cls(
            speaker=str(data.get("speaker") or "Speaker"),
            text=str(data.get("text") or ""),
            timestamp=(str(data["timestamp"]) if data.get("timestamp") else None),
        )


@dataclass
class CallRecordingTranscript:
    """The transcript and summary of one call recording (at most one each).

    The state machine is ``PENDING -> PROCESSING -> COMPLETED | FAILED``; a
    FAILED (or abandoned) transcript can be queued again.
    """

    id: UUID
    recording_id: UUID
    call_id: UUID
    status: TranscriptionStatus
    requested_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    transcript_text: str | None = None
    segments: list[TranscriptSegment] = field(default_factory=list)
    summary: str | None = None
    key_points: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    language: str | None = None
    model_name: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # -- creation ---------------------------------------------------------

    @classmethod
    def create_pending(
        cls,
        *,
        recording_id: UUID,
        call_id: UUID,
        requested_by_id: UUID | None,
    ) -> "CallRecordingTranscript":
        if recording_id is None or call_id is None:
            raise ValueError("Recording and call are required.")

        now = datetime.now(timezone.utc)

        return cls(
            id=uuid4(),
            recording_id=recording_id,
            call_id=call_id,
            status=TranscriptionStatus.PENDING,
            requested_by_id=requested_by_id,
            created_at=now,
            updated_at=now,
        )

    # -- state transitions ------------------------------------------------

    def queue_again(self, requested_by_id: UUID | None) -> None:
        """Throw the previous attempt away and wait for a new run."""
        self.status = TranscriptionStatus.PENDING
        self.requested_by_id = requested_by_id
        self.transcript_text = None
        self.segments = []
        self.summary = None
        self.key_points = []
        self.action_items = []
        self.language = None
        self.model_name = None
        self.error_message = None
        self.started_at = None
        self.completed_at = None
        self._touch()

    def mark_processing(self) -> None:
        if self.status != TranscriptionStatus.PENDING:
            raise ValueError("Only a queued transcription can be started.")

        self.status = TranscriptionStatus.PROCESSING
        self.started_at = datetime.now(timezone.utc)
        self.error_message = None
        self._touch()

    def mark_completed(
        self,
        *,
        transcript_text: str,
        segments: list[TranscriptSegment],
        summary: str,
        key_points: list[str],
        action_items: list[str],
        language: str | None,
        model_name: str | None,
    ) -> None:
        self.status = TranscriptionStatus.COMPLETED
        self.transcript_text = transcript_text
        self.segments = list(segments)
        self.summary = summary
        self.key_points = list(key_points)
        self.action_items = list(action_items)
        self.language = language
        self.model_name = model_name
        self.error_message = None
        self.completed_at = datetime.now(timezone.utc)
        self._touch()

    def mark_failed(self, message: str) -> None:
        self.status = TranscriptionStatus.FAILED
        self.error_message = (message or "Transcription failed.")[:MAX_ERROR_MESSAGE_LENGTH]
        self.completed_at = datetime.now(timezone.utc)
        self._touch()

    # -- queries ----------------------------------------------------------

    def is_stale(self, *, now: datetime | None = None, after: timedelta) -> bool:
        """An active run that has not moved for ``after``: its worker is gone.

        Threads die with the server process (deploy, crash), so a transcript
        can stay PENDING / PROCESSING forever. Once stale it may be queued again.
        """
        if not self.status.is_active:
            return False

        return (now or datetime.now(timezone.utc)) - self.updated_at > after

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def copy(self) -> "CallRecordingTranscript":
        return replace(self)
