from datetime import timedelta
from uuid import UUID

from src.modules.calls.application.dto.call_recording_transcript import (
    RecordingTranscriptDTO,
    RequestTranscriptionDTO,
)
from src.modules.calls.application.interfaces.call_recording_repository import (
    CallRecordingRepository,
)
from src.modules.calls.application.interfaces.call_recording_transcript_repository import (
    CallRecordingTranscriptRepository,
)
from src.modules.calls.application.interfaces.call_repository import CallRepository
from src.modules.calls.application.interfaces.transcription_dispatcher import (
    TranscriptionDispatcher,
)
from src.modules.calls.application.interfaces.transcription_service import (
    TranscriptionService,
    TranscriptionUnavailableError,
)
from src.modules.calls.domain.entities.call_recording_transcript import (
    CallRecordingTranscript,
)
from src.modules.calls.domain.enums.transcription_status import TranscriptionStatus
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)

DEFAULT_STALE_AFTER = timedelta(minutes=15)


class RequestRecordingTranscriptionUseCase:
    """Queue the transcript + summary of a recording.

    Idempotent: asking again while a run is active, or after it finished,
    returns what is there instead of paying for a second transcription.
    A FAILED run, an abandoned run (worker died) or ``regenerate=True``
    queues a fresh one.
    """

    NOT_CONFIGURED_MESSAGE = "Call transcription is not configured on the server."

    def __init__(
        self,
        call_repository: CallRepository,
        recording_repository: CallRecordingRepository,
        transcript_repository: CallRecordingTranscriptRepository,
        transcription_service: TranscriptionService,
        dispatcher: TranscriptionDispatcher,
        transaction_manager: TransactionManager,
        stale_after: timedelta = DEFAULT_STALE_AFTER,
    ):
        self.call_repository = call_repository
        self.recording_repository = recording_repository
        self.transcript_repository = transcript_repository
        self.transcription_service = transcription_service
        self.dispatcher = dispatcher
        self.transaction_manager = transaction_manager
        self.stale_after = stale_after

    def execute(self, data: RequestTranscriptionDTO) -> RecordingTranscriptDTO:
        if self.call_repository.get_by_id(data.call_id) is None:
            raise ValueError("Call not found.")

        recording = self.recording_repository.get_by_id(data.recording_id, data.call_id)

        if recording is None:
            raise ValueError("Recording not found.")

        if not self.transcription_service.is_configured():
            raise TranscriptionUnavailableError(self.NOT_CONFIGURED_MESSAGE)

        existing = self.transcript_repository.get_by_recording_id(recording.id)

        if existing is not None and not self._should_queue_again(existing, data):
            return RecordingTranscriptDTO(recording.id, recording.call_id, existing)

        def queue() -> tuple[UUID, CallRecordingTranscript]:
            if existing is None:
                transcript = CallRecordingTranscript.create_pending(
                    recording_id=recording.id,
                    call_id=recording.call_id,
                    requested_by_id=data.requested_by_id,
                )
            else:
                transcript = existing
                transcript.queue_again(data.requested_by_id)

            return transcript.id, self.transcript_repository.save(transcript)

        wanted_id, queued = self.transaction_manager.execute(queue)

        # A concurrent request queued it first (double click, or the upload
        # hook racing a manual request): that run is already on its way.
        if queued.id != wanted_id:
            return RecordingTranscriptDTO(recording.id, recording.call_id, queued)

        # After the commit, so the worker is sure to find the row.
        try:
            self.dispatcher.dispatch(queued.recording_id)
        except Exception as error:
            queued.mark_failed("The transcription could not be started. Try again.")
            self.transcript_repository.save(queued)
            raise error

        # A dispatcher that runs inline has finished by now; return its result.
        current = self.transcript_repository.get_by_recording_id(recording.id) or queued

        return RecordingTranscriptDTO(recording.id, recording.call_id, current)

    def _should_queue_again(
        self,
        existing: CallRecordingTranscript,
        data: RequestTranscriptionDTO,
    ) -> bool:
        if existing.status.is_active:
            return existing.is_stale(after=self.stale_after)

        if existing.status == TranscriptionStatus.FAILED:
            return True

        return data.regenerate  # COMPLETED
