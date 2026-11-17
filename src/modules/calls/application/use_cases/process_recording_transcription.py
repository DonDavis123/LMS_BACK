import logging
from uuid import UUID

from src.modules.calls.application.interfaces.call_recording_repository import (
    CallRecordingRepository,
)
from src.modules.calls.application.interfaces.call_recording_transcript_repository import (
    CallRecordingTranscriptRepository,
)
from src.modules.calls.application.interfaces.recording_storage import (
    RecordingStorage,
)
from src.modules.calls.application.interfaces.transcription_service import (
    TranscriptionError,
    TranscriptionService,
)
from src.modules.calls.domain.enums.transcription_status import TranscriptionStatus

logger = logging.getLogger(__name__)


class ProcessRecordingTranscriptionUseCase:
    """Does the actual work for a queued transcript: audio in, text + summary out.

    Runs in the background, so it never raises: every outcome is written to the
    transcript row (COMPLETED or FAILED) where the client's next poll sees it.
    """

    AUDIO_MISSING_MESSAGE = "The recording file is no longer available."
    UNEXPECTED_MESSAGE = "Transcription failed unexpectedly. Try again later."

    def __init__(
        self,
        recording_repository: CallRecordingRepository,
        transcript_repository: CallRecordingTranscriptRepository,
        storage: RecordingStorage,
        transcription_service: TranscriptionService,
    ):
        self.recording_repository = recording_repository
        self.transcript_repository = transcript_repository
        self.storage = storage
        self.transcription_service = transcription_service

    def execute(self, recording_id: UUID) -> None:
        transcript = self.transcript_repository.get_by_recording_id(recording_id)

        # Gone, or another worker / a newer request already owns it.
        if transcript is None or transcript.status != TranscriptionStatus.PENDING:
            return

        transcript.mark_processing()
        self.transcript_repository.save(transcript)

        try:
            result = self._transcribe(transcript.recording_id, transcript.call_id)
        except TranscriptionError as error:
            logger.warning(
                "Transcription of recording %s failed: %s", recording_id, error
            )
            transcript.mark_failed(error.user_message)
        except Exception:
            logger.exception("Transcription of recording %s crashed", recording_id)
            transcript.mark_failed(self.UNEXPECTED_MESSAGE)
        else:
            transcript.mark_completed(
                transcript_text=result.transcript_text,
                segments=result.segments,
                summary=result.summary,
                key_points=result.key_points,
                action_items=result.action_items,
                language=result.language,
                model_name=result.model_name,
            )

        try:
            self.transcript_repository.save(transcript)
        except Exception:
            logger.exception(
                "Could not save the transcript of recording %s", recording_id
            )

    def _transcribe(self, recording_id: UUID, call_id: UUID):
        recording = self.recording_repository.get_by_id(recording_id, call_id)

        if recording is None:
            raise TranscriptionError("Recording not found.")

        try:
            audio = self.storage.open(recording.storage_key)
        except FileNotFoundError:
            raise TranscriptionError(self.AUDIO_MISSING_MESSAGE)

        try:
            content = audio.read()
        finally:
            audio.close()

        return self.transcription_service.transcribe(
            audio=content,
            content_type=recording.content_type,
            file_name=recording.file_name,
        )
