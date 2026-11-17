"""API tests for call recording transcription + summary.

  * ``GET/POST /api/calls/<id>/recordings/<id>/transcript/``
  * automatic transcription right after an upload

Gemini is never called: ``GeminiTranscriptionService.transcribe`` is mocked.
Jobs run inline (``CALL_TRANSCRIPTION_RUN_INLINE``) so no thread outlives a test.
"""

from unittest.mock import patch

from django.test import override_settings
from rest_framework import status

from src.modules.calls.application.dto.call_recording_transcript import (
    TranscriptionResult,
)
from src.modules.calls.application.interfaces.transcription_service import (
    TranscriptionError,
)
from src.modules.calls.domain.entities.call_recording_transcript import (
    TranscriptSegment,
)
from src.modules.calls.infrastructure.persistence.models import (
    DjangoCallRecordingModel,
    DjangoCallRecordingTranscriptModel,
)
from src.modules.calls.infrastructure.transcription.gemini_transcription_service import (
    GeminiTranscriptionService,
)
from src.modules.calls.infrastructure.transcription.thread_transcription_dispatcher import (
    ThreadTranscriptionDispatcher,
)
from src.modules.calls.tests_recordings_api import (
    AUDIO,
    CallRecordingApiTestCase,
)
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

RESULT = TranscriptionResult(
    transcript_text="[00:01] Agent: Hello",
    summary="A short follow-up call.",
    segments=[TranscriptSegment("Agent", "Hello", "00:01")],
    key_points=["Greeting"],
    action_items=["Send the quote"],
    language="English",
    model_name="gemini-test",
)

GEMINI_ON = {
    "GEMINI_API_KEY": "test-key",
    "CALL_TRANSCRIPTION_RUN_INLINE": True,
    "CALL_TRANSCRIPTION_AUTO": True,
}


class TranscriptionApiTestCase(CallRecordingApiTestCase):
    def _transcript_url(self, recording_id, call_id=None):
        return self._url(recording_id, "transcript", call_id=call_id)

    def _recording_id(self):
        return DjangoCallRecordingModel.objects.get().id


@override_settings(**{**GEMINI_ON, "CALL_TRANSCRIPTION_AUTO": False})
class RequestTranscriptApiTests(TranscriptionApiTestCase):
    def setUp(self):
        super().setUp()
        self.recording = self._upload_ok()
        self.url = self._transcript_url(self.recording["id"])

    def test_recording_never_transcribed_reports_not_requested(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "NOT_REQUESTED")
        self.assertIsNone(response.data["summary"])
        self.assertEqual(response.data["segments"], [])

    @patch.object(GeminiTranscriptionService, "transcribe", return_value=RESULT)
    def test_post_transcribes_and_get_returns_the_result(self, transcribe):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertEqual(response.data["summary"], "A short follow-up call.")
        self.assertEqual(response.data["transcript"], "[00:01] Agent: Hello")
        self.assertEqual(response.data["key_points"], ["Greeting"])
        self.assertEqual(response.data["action_items"], ["Send the quote"])
        self.assertEqual(response.data["language"], "English")
        self.assertEqual(
            response.data["segments"],
            [{"speaker": "Agent", "timestamp": "00:01", "text": "Hello"}],
        )

        fetched = self.client.get(self.url)
        self.assertEqual(fetched.data["status"], "COMPLETED")

        # The audio that reached the service is the uploaded audio.
        self.assertEqual(transcribe.call_args.kwargs["audio"], AUDIO)
        self.assertEqual(transcribe.call_args.kwargs["content_type"], "audio/mpeg")

    @patch.object(ThreadTranscriptionDispatcher, "dispatch")
    def test_post_answers_202_while_the_work_is_queued(self, dispatch):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        self.assertEqual(response.data["status"], "PENDING")
        dispatch.assert_called_once()

        again = self.client.post(self.url, {}, format="json")
        self.assertEqual(again.status_code, status.HTTP_202_ACCEPTED)
        dispatch.assert_called_once()  # no second run while one is active

    @patch.object(
        GeminiTranscriptionService,
        "transcribe",
        side_effect=TranscriptionError("The service is busy."),
    )
    def test_failure_is_visible_and_can_be_retried(self, transcribe):
        failed = self.client.post(self.url, {}, format="json")

        self.assertEqual(failed.status_code, status.HTTP_200_OK)
        self.assertEqual(failed.data["status"], "FAILED")
        self.assertEqual(failed.data["error_message"], "The service is busy.")

        transcribe.side_effect = None
        transcribe.return_value = RESULT
        retried = self.client.post(self.url, {}, format="json")

        self.assertEqual(retried.data["status"], "COMPLETED")
        self.assertIsNone(retried.data["error_message"])
        self.assertEqual(DjangoCallRecordingTranscriptModel.objects.count(), 1)

    @patch.object(GeminiTranscriptionService, "transcribe", return_value=RESULT)
    def test_regenerate_only_when_asked(self, transcribe):
        self.client.post(self.url, {}, format="json")
        self.client.post(self.url, {}, format="json")
        self.assertEqual(transcribe.call_count, 1)

        self.client.post(self.url, {"regenerate": True}, format="json")
        self.assertEqual(transcribe.call_count, 2)

    @override_settings(GEMINI_API_KEY="")
    def test_post_without_an_api_key_answers_503(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(DjangoCallRecordingTranscriptModel.objects.exists())

    def test_unknown_recording_and_call_are_404(self):
        unknown = "00000000-0000-0000-0000-000000000001"

        self.assertEqual(
            self.client.get(self._transcript_url(unknown)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.post(self._transcript_url(unknown), {}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(
                self._transcript_url(self.recording["id"], call_id=unknown)
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_requires_authentication(self):
        from rest_framework.test import APIClient

        self.assertIn(
            APIClient().get(self.url).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    @patch.object(GeminiTranscriptionService, "transcribe", return_value=RESULT)
    def test_deleting_the_recording_deletes_its_transcript(self, _):
        self.client.post(self.url, {}, format="json")
        self.assertEqual(DjangoCallRecordingTranscriptModel.objects.count(), 1)

        response = self.client.delete(self._url(self.recording["id"]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(DjangoCallRecordingTranscriptModel.objects.exists())


@override_settings(**GEMINI_ON)
class AutoTranscriptionApiTests(TranscriptionApiTestCase):
    @patch.object(GeminiTranscriptionService, "transcribe", return_value=RESULT)
    def test_upload_transcribes_the_recording(self, transcribe):
        recording = self._upload_ok()

        transcript = self.client.get(self._transcript_url(recording["id"]))

        self.assertEqual(transcript.data["status"], "COMPLETED")
        self.assertEqual(transcript.data["summary"], "A short follow-up call.")
        transcribe.assert_called_once()

    @patch.object(
        GeminiTranscriptionService,
        "transcribe",
        side_effect=TranscriptionError("The service is busy."),
    )
    def test_a_failing_transcription_never_fails_the_upload(self, _):
        response = self._upload()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            self.client.get(self._transcript_url(response.data["id"])).data["status"],
            "FAILED",
        )

    @override_settings(CALL_TRANSCRIPTION_AUTO=False)
    @patch.object(GeminiTranscriptionService, "transcribe", return_value=RESULT)
    def test_auto_transcription_can_be_switched_off(self, transcribe):
        recording = self._upload_ok()

        self.assertEqual(
            self.client.get(self._transcript_url(recording["id"])).data["status"],
            "NOT_REQUESTED",
        )
        transcribe.assert_not_called()

    @override_settings(GEMINI_API_KEY="")
    def test_upload_without_an_api_key_behaves_as_before(self):
        recording = self._upload_ok()

        self.assertEqual(
            self.client.get(self._transcript_url(recording["id"])).data["status"],
            "NOT_REQUESTED",
        )


@override_settings(**{**GEMINI_ON, "CALL_TRANSCRIPTION_AUTO": False})
class TranscriptTenantIsolationTests(TranscriptionApiTestCase):
    @patch.object(GeminiTranscriptionService, "transcribe", return_value=RESULT)
    def test_other_company_cannot_read_or_start_a_transcript(self, _):
        recording = self._upload_ok()
        url = self._transcript_url(recording["id"])
        self.client.post(url, {}, format="json")

        other_client = authenticated_client(
            make_user(
                make_company("Other Company"),
                User.Role.ADMIN,
                email="other-company@example.com",
            )
        )

        self.assertEqual(other_client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            other_client.post(url, {}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
