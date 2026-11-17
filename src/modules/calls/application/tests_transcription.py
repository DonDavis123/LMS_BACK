"""Use-case tests for call recording transcription (no database, no network).

The use cases only see the repository / storage / service / dispatcher
interfaces, so in-memory fakes cover the rules.
"""

import io
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.calls.application.dto.call_recording_transcript import (
    RequestTranscriptionDTO,
    TranscriptionResult,
)
from src.modules.calls.application.interfaces.transcription_service import (
    TranscriptionError,
    TranscriptionUnavailableError,
)
from src.modules.calls.application.tests_recordings import (
    FakeCallRepo,
    FakeRecordingRepo,
    FakeStorage,
    FakeTimelineRecorder,
    FakeTransaction,
    MB,
    make_call,
)
from src.modules.calls.application.use_cases.get_recording_transcript import (
    GetRecordingTranscriptUseCase,
)
from src.modules.calls.application.use_cases.process_recording_transcription import (
    ProcessRecordingTranscriptionUseCase,
)
from src.modules.calls.application.use_cases.request_recording_transcription import (
    RequestRecordingTranscriptionUseCase,
)
from src.modules.calls.application.use_cases.upload_call_recording import (
    UploadCallRecordingUseCase,
)
from src.modules.calls.application.dto.call_recording import UploadCallRecordingDTO
from src.modules.calls.domain.entities.call_recording import CallRecording
from src.modules.calls.domain.entities.call_recording_transcript import (
    CallRecordingTranscript,
    TranscriptSegment,
)
from src.modules.calls.domain.enums.transcription_status import TranscriptionStatus


class FakeTranscriptRepo:
    def __init__(self):
        self.rows = {}

    def save(self, transcript):
        # An existing row for the recording wins (what the real repository does
        # when a concurrent request got there first).
        for row in self.rows.values():
            if row.recording_id == transcript.recording_id and row.id != transcript.id:
                return row.copy()
        self.rows[transcript.id] = transcript.copy()
        return transcript.copy()

    def get_by_recording_id(self, recording_id):
        for row in self.rows.values():
            if row.recording_id == recording_id:
                return row.copy()
        return None


class FakeService:
    def __init__(self, configured=True, result=None, error=None):
        self.configured = configured
        self.result = result or TranscriptionResult(
            transcript_text="Agent: Hello",
            summary="A short call.",
            segments=[TranscriptSegment("Agent", "Hello", "00:01")],
            key_points=["Greeting"],
            action_items=["Send quote"],
            language="English",
            model_name="gemini-test",
        )
        self.error = error
        self.calls = []

    def is_configured(self):
        return self.configured

    def transcribe(self, *, audio, content_type, file_name):
        self.calls.append((audio, content_type, file_name))
        if self.error is not None:
            raise self.error
        return self.result


class FakeDispatcher:
    def __init__(self, run=None, error=None):
        self.dispatched = []
        self.run = run
        self.error = error

    def dispatch(self, recording_id):
        if self.error is not None:
            raise self.error
        self.dispatched.append(recording_id)
        if self.run is not None:
            self.run(recording_id)


class TranscriptionTestBase(unittest.TestCase):
    def setUp(self):
        self.call = make_call()
        self.calls = FakeCallRepo(self.call)
        self.recordings = FakeRecordingRepo()
        self.transcripts = FakeTranscriptRepo()
        self.storage = FakeStorage()
        self.service = FakeService()
        self.user_id = uuid4()

        recording = CallRecording.create(
            call_id=self.call.id,
            uploaded_by_id=self.user_id,
            file_name="call.mp3",
            content_type="audio/mpeg",
            size_bytes=9,
            max_size_bytes=25 * MB,
        )
        recording.storage_key = self.storage.store(
            call_id=self.call.id,
            recording_id=recording.id,
            extension=".mp3",
            content=io.BytesIO(b"audio-bytes"),
        )
        self.recording = self.recordings.save(recording)

    def processor(self, service=None):
        return ProcessRecordingTranscriptionUseCase(
            self.recordings,
            self.transcripts,
            self.storage,
            service or self.service,
        )

    def requester(self, dispatcher=None, service=None, stale_after=timedelta(minutes=15)):
        return RequestRecordingTranscriptionUseCase(
            self.calls,
            self.recordings,
            self.transcripts,
            service or self.service,
            dispatcher or FakeDispatcher(),
            FakeTransaction(),
            stale_after=stale_after,
        )

    def request(self, **kwargs):
        return RequestTranscriptionDTO(
            call_id=self.call.id,
            recording_id=self.recording.id,
            requested_by_id=self.user_id,
            **kwargs,
        )

    def stored(self):
        return self.transcripts.get_by_recording_id(self.recording.id)


class RequestRecordingTranscriptionTests(TranscriptionTestBase):
    def test_queues_a_pending_transcript_and_dispatches_it(self):
        dispatcher = FakeDispatcher()

        result = self.requester(dispatcher).execute(self.request())

        self.assertEqual(result.transcript.status, TranscriptionStatus.PENDING)
        self.assertEqual(result.transcript.requested_by_id, self.user_id)
        self.assertEqual(dispatcher.dispatched, [self.recording.id])
        self.assertEqual(self.stored().status, TranscriptionStatus.PENDING)

    def test_unknown_call_is_rejected(self):
        data = RequestTranscriptionDTO(call_id=uuid4(), recording_id=self.recording.id)

        with self.assertRaisesRegex(ValueError, "Call not found."):
            self.requester().execute(data)

    def test_recording_of_another_call_is_rejected(self):
        other_call = make_call()
        self.calls.calls[other_call.id] = other_call
        data = RequestTranscriptionDTO(call_id=other_call.id, recording_id=self.recording.id)

        with self.assertRaisesRegex(ValueError, "Recording not found."):
            self.requester().execute(data)

    def test_not_configured_is_reported_and_nothing_is_queued(self):
        dispatcher = FakeDispatcher()
        service = FakeService(configured=False)

        with self.assertRaises(TranscriptionUnavailableError):
            self.requester(dispatcher, service).execute(self.request())

        self.assertIsNone(self.stored())
        self.assertEqual(dispatcher.dispatched, [])

    def test_asking_again_while_active_does_not_dispatch_twice(self):
        dispatcher = FakeDispatcher()
        use_case = self.requester(dispatcher)

        first = use_case.execute(self.request())
        second = use_case.execute(self.request())

        self.assertEqual(first.transcript.id, second.transcript.id)
        self.assertEqual(len(dispatcher.dispatched), 1)

    def test_completed_transcript_is_returned_without_a_new_run(self):
        dispatcher = FakeDispatcher(run=self.processor().execute)
        use_case = self.requester(dispatcher)
        use_case.execute(self.request())

        again = use_case.execute(self.request())

        self.assertEqual(again.transcript.status, TranscriptionStatus.COMPLETED)
        self.assertEqual(len(self.service.calls), 1)

    def test_regenerate_runs_again(self):
        dispatcher = FakeDispatcher(run=self.processor().execute)
        use_case = self.requester(dispatcher)
        first = use_case.execute(self.request())

        again = use_case.execute(self.request(regenerate=True))

        self.assertEqual(len(self.service.calls), 2)
        self.assertEqual(again.transcript.id, first.transcript.id)  # same row reused
        self.assertEqual(again.transcript.status, TranscriptionStatus.COMPLETED)

    def test_failed_transcript_is_queued_again(self):
        failing = FakeService(error=TranscriptionError("Quota used up."))
        dispatcher = FakeDispatcher(run=self.processor(failing).execute)
        self.requester(dispatcher, failing).execute(self.request())
        self.assertEqual(self.stored().status, TranscriptionStatus.FAILED)

        retry_dispatcher = FakeDispatcher(run=self.processor().execute)
        result = self.requester(retry_dispatcher).execute(self.request())

        self.assertEqual(result.transcript.status, TranscriptionStatus.COMPLETED)
        self.assertIsNone(result.transcript.error_message)

    def test_abandoned_run_is_queued_again(self):
        dispatcher = FakeDispatcher()
        use_case = self.requester(dispatcher, stale_after=timedelta(minutes=15))
        use_case.execute(self.request())

        row = self.transcripts.rows[self.stored().id]
        row.updated_at = datetime.now(timezone.utc) - timedelta(minutes=16)

        use_case.execute(self.request())

        self.assertEqual(len(dispatcher.dispatched), 2)

    def test_dispatch_failure_marks_the_transcript_failed(self):
        dispatcher = FakeDispatcher(error=RuntimeError("pool is gone"))

        with self.assertRaises(RuntimeError):
            self.requester(dispatcher).execute(self.request())

        self.assertEqual(self.stored().status, TranscriptionStatus.FAILED)

    def test_concurrent_request_does_not_dispatch_a_second_run(self):
        # Another request already stored a transcript for the recording.
        winner = CallRecordingTranscript.create_pending(
            recording_id=self.recording.id,
            call_id=self.call.id,
            requested_by_id=None,
        )
        dispatcher = FakeDispatcher()
        use_case = self.requester(dispatcher)

        # Make the "existing" lookup miss, as it would for a request that
        # started before the winner committed.
        original_get = self.transcripts.get_by_recording_id
        self.transcripts.get_by_recording_id = lambda recording_id: None
        self.transcripts.rows[winner.id] = winner

        result = use_case.execute(self.request())
        self.transcripts.get_by_recording_id = original_get

        self.assertEqual(result.transcript.id, winner.id)
        self.assertEqual(dispatcher.dispatched, [])


class ProcessRecordingTranscriptionTests(TranscriptionTestBase):
    def queue(self):
        self.requester().execute(self.request())

    def test_success_stores_transcript_and_summary(self):
        self.queue()

        self.processor().execute(self.recording.id)

        transcript = self.stored()
        self.assertEqual(transcript.status, TranscriptionStatus.COMPLETED)
        self.assertEqual(transcript.summary, "A short call.")
        self.assertEqual(transcript.transcript_text, "Agent: Hello")
        self.assertEqual(transcript.key_points, ["Greeting"])
        self.assertEqual(transcript.action_items, ["Send quote"])
        self.assertEqual(transcript.language, "English")
        self.assertEqual(transcript.model_name, "gemini-test")
        self.assertIsNotNone(transcript.completed_at)
        self.assertEqual(
            self.service.calls, [(b"audio-bytes", "audio/mpeg", "call.mp3")]
        )

    def test_service_error_is_stored_as_failed_with_its_safe_message(self):
        self.queue()
        service = FakeService(error=TranscriptionError("The service is busy."))

        self.processor(service).execute(self.recording.id)

        transcript = self.stored()
        self.assertEqual(transcript.status, TranscriptionStatus.FAILED)
        self.assertEqual(transcript.error_message, "The service is busy.")

    def test_unexpected_crash_never_leaks_its_details(self):
        self.queue()
        service = FakeService(error=RuntimeError("secret key abc123 rejected"))

        self.processor(service).execute(self.recording.id)

        transcript = self.stored()
        self.assertEqual(transcript.status, TranscriptionStatus.FAILED)
        self.assertNotIn("abc123", transcript.error_message)

    def test_missing_audio_file_is_a_failure_not_a_crash(self):
        self.queue()
        self.storage.files.clear()

        self.processor().execute(self.recording.id)

        transcript = self.stored()
        self.assertEqual(transcript.status, TranscriptionStatus.FAILED)
        self.assertEqual(
            transcript.error_message,
            ProcessRecordingTranscriptionUseCase.AUDIO_MISSING_MESSAGE,
        )

    def test_only_a_pending_transcript_is_processed(self):
        self.queue()
        self.processor().execute(self.recording.id)

        self.processor().execute(self.recording.id)  # already COMPLETED

        self.assertEqual(len(self.service.calls), 1)

    def test_nothing_happens_without_a_transcript(self):
        self.processor().execute(uuid4())

        self.assertEqual(self.service.calls, [])


class GetRecordingTranscriptTests(TranscriptionTestBase):
    def use_case(self):
        return GetRecordingTranscriptUseCase(self.calls, self.recordings, self.transcripts)

    def test_recording_never_transcribed_has_no_transcript(self):
        result = self.use_case().execute(self.call.id, self.recording.id)

        self.assertIsNone(result.transcript)
        self.assertEqual(result.recording_id, self.recording.id)

    def test_returns_the_stored_transcript(self):
        self.requester().execute(self.request())

        result = self.use_case().execute(self.call.id, self.recording.id)

        self.assertEqual(result.transcript.status, TranscriptionStatus.PENDING)

    def test_unknown_call_and_recording_are_not_found(self):
        with self.assertRaisesRegex(ValueError, "Call not found."):
            self.use_case().execute(uuid4(), self.recording.id)

        with self.assertRaisesRegex(ValueError, "Recording not found."):
            self.use_case().execute(self.call.id, uuid4())


class UploadHookTests(TranscriptionTestBase):
    def upload_use_case(self, on_uploaded):
        class Timeline(FakeTimelineRecorder):
            pass

        return UploadCallRecordingUseCase(
            self.calls,
            self.recordings_with_total(),
            self.storage,
            Timeline(),
            FakeTransaction(),
            on_uploaded=on_uploaded,
        )

    def recordings_with_total(self):
        self.recordings.total_size_bytes = lambda: 0
        return self.recordings

    def dto(self):
        return UploadCallRecordingDTO(
            call_id=self.call.id,
            uploaded_by_id=self.user_id,
            file_name="second.mp3",
            content_type="audio/mpeg",
            size_bytes=5,
            content=io.BytesIO(b"12345"),
        )

    def test_hook_receives_the_saved_recording(self):
        seen = []

        created = self.upload_use_case(seen.append).execute(self.dto())

        self.assertEqual([item.recording.id for item in seen], [created.recording.id])

    def test_failing_hook_does_not_fail_the_upload(self):
        def broken(_):
            raise RuntimeError("transcription is down")

        created = self.upload_use_case(broken).execute(self.dto())

        self.assertEqual(created.recording.file_name, "second.mp3")

    def test_upload_works_without_a_hook(self):
        created = self.upload_use_case(None).execute(self.dto())

        self.assertEqual(created.recording.file_name, "second.mp3")


class TranscriptEntityTests(unittest.TestCase):
    def test_cannot_start_a_transcript_that_is_not_pending(self):
        transcript = CallRecordingTranscript.create_pending(
            recording_id=uuid4(), call_id=uuid4(), requested_by_id=None
        )
        transcript.mark_processing()

        with self.assertRaises(ValueError):
            transcript.mark_processing()

    def test_long_error_messages_are_cut_to_the_column_size(self):
        transcript = CallRecordingTranscript.create_pending(
            recording_id=uuid4(), call_id=uuid4(), requested_by_id=None
        )

        transcript.mark_failed("x" * 2000)

        self.assertEqual(len(transcript.error_message), 500)

    def test_finished_transcripts_are_never_stale(self):
        transcript = CallRecordingTranscript.create_pending(
            recording_id=uuid4(), call_id=uuid4(), requested_by_id=None
        )
        transcript.mark_failed("nope")
        transcript.updated_at = datetime.now(timezone.utc) - timedelta(days=3)

        self.assertFalse(transcript.is_stale(after=timedelta(minutes=15)))


if __name__ == "__main__":
    unittest.main()
