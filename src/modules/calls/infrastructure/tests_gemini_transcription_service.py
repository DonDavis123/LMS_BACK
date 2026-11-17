"""Tests for the Gemini client. HTTP is mocked: no network, no API key."""

import base64
import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from src.modules.calls.application.interfaces.transcription_service import (
    TranscriptionError,
)
from src.modules.calls.infrastructure.transcription import (
    gemini_transcription_service as gemini,
)
from src.modules.calls.infrastructure.transcription.gemini_transcription_service import (
    GeminiConfig,
    GeminiTranscriptionService,
    gemini_mime_type,
)

GOOD_ANSWER = {
    "language": "Malayalam",
    "segments": [
        {"speaker": "Agent", "timestamp": "00:02", "text": "Hello, this is Asha."},
        {"speaker": "Customer", "timestamp": "bad", "text": "Hi, tell me more."},
        {"speaker": "Agent", "timestamp": "01:10", "text": "   "},
    ],
    "summary": "Asha called to follow up on the quote.",
    "key_points": ["Quote sent", "", "Wants a discount"],
    "action_items": ["Send revised quote by Friday"],
}


def http_response(status=200, body=None, headers=None, text=None):
    response = MagicMock(spec=requests.Response)
    response.status_code = status
    response.ok = status < 400
    response.headers = headers or {}
    response.text = text if text is not None else json.dumps(body or {})
    response.json.side_effect = lambda: json.loads(response.text)
    return response


def gemini_answer(payload, finish="STOP"):
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": json.dumps(payload)}]},
                "finishReason": finish,
            }
        ]
    }


def service(**overrides):
    config = {"api_key": "test-key", "max_retries": 2}
    config.update(overrides)
    return GeminiTranscriptionService(GeminiConfig(**config))


@patch.object(gemini.time, "sleep", lambda *_: None)
class GeminiTranscriptionServiceTests(unittest.TestCase):
    def transcribe(self, svc=None, audio=b"abc", content_type="audio/mpeg"):
        return (svc or service()).transcribe(
            audio=audio, content_type=content_type, file_name="call.mp3"
        )

    # -- configuration ----------------------------------------------------

    def test_not_configured_without_an_api_key(self):
        self.assertFalse(service(api_key="").is_configured())
        self.assertFalse(service(api_key="   ").is_configured())
        self.assertTrue(service().is_configured())

    @patch.object(gemini.requests, "request")
    def test_transcribe_refuses_to_call_google_without_a_key(self, request):
        with self.assertRaises(TranscriptionError):
            self.transcribe(service(api_key=""))

        request.assert_not_called()

    # -- request shape ------------------------------------------------------

    @patch.object(gemini.requests, "request")
    def test_small_audio_goes_inline_with_the_key_in_a_header(self, request):
        request.return_value = http_response(body=gemini_answer(GOOD_ANSWER))

        self.transcribe(audio=b"audio-bytes")

        (method, url), kwargs = request.call_args
        self.assertEqual(method, "POST")
        self.assertEqual(
            url,
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-2.5-flash:generateContent",
        )
        self.assertNotIn("test-key", url)  # never in the URL (logs!)
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-key")

        parts = kwargs["json"]["contents"][0]["parts"]
        self.assertEqual(
            parts[0]["inlineData"],
            {
                "mimeType": "audio/mp3",
                "data": base64.b64encode(b"audio-bytes").decode(),
            },
        )
        config = kwargs["json"]["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertIn("segments", config["responseSchema"]["properties"])

    @patch.object(gemini.requests, "request")
    def test_prompt_asks_for_the_configured_summary_language(self, request):
        request.return_value = http_response(body=gemini_answer(GOOD_ANSWER))

        self.transcribe(service(summary_language="Hindi"))

        prompt = request.call_args.kwargs["json"]["contents"][0]["parts"][1]["text"]
        self.assertIn("in Hindi", prompt)

    @patch.object(gemini.requests, "request")
    def test_model_name_may_already_have_the_models_prefix(self, request):
        request.return_value = http_response(body=gemini_answer(GOOD_ANSWER))

        self.transcribe(service(model="models/gemini-test"))

        self.assertIn("/v1beta/models/gemini-test:generateContent", request.call_args.args[1])

    # -- response -> result ---------------------------------------------------

    @patch.object(gemini.requests, "request")
    def test_parses_and_cleans_the_answer(self, request):
        request.return_value = http_response(body=gemini_answer(GOOD_ANSWER))

        result = self.transcribe()

        self.assertEqual(result.summary, "Asha called to follow up on the quote.")
        self.assertEqual(result.language, "Malayalam")
        self.assertEqual(result.key_points, ["Quote sent", "Wants a discount"])
        self.assertEqual(result.action_items, ["Send revised quote by Friday"])
        self.assertEqual(result.model_name, "gemini-2.5-flash")
        # The blank turn is dropped, the malformed timestamp becomes None.
        self.assertEqual(
            [(s.speaker, s.timestamp) for s in result.segments],
            [("Agent", "00:02"), ("Customer", None)],
        )
        self.assertEqual(
            result.transcript_text,
            "[00:02] Agent: Hello, this is Asha.\nCustomer: Hi, tell me more.",
        )

    @patch.object(gemini.requests, "request")
    def test_json_wrapped_in_a_code_fence_is_accepted(self, request):
        fenced = "```json\n" + json.dumps(GOOD_ANSWER) + "\n```"
        request.return_value = http_response(
            body={"candidates": [{"content": {"parts": [{"text": fenced}]}}]}
        )

        self.assertEqual(self.transcribe().language, "Malayalam")

    @patch.object(gemini.requests, "request")
    def test_thinking_parts_are_ignored(self, request):
        request.return_value = http_response(
            body={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "let me think...", "thought": True},
                                {"text": json.dumps(GOOD_ANSWER)},
                            ]
                        }
                    }
                ]
            }
        )

        self.assertEqual(self.transcribe().language, "Malayalam")

    @patch.object(gemini.requests, "request")
    def test_silence_is_reported_as_no_speech(self, request):
        empty = {"language": "", "segments": [], "summary": "", "key_points": [], "action_items": []}
        request.return_value = http_response(body=gemini_answer(empty))

        with self.assertRaisesRegex(TranscriptionError, "No speech"):
            self.transcribe()

    @patch.object(gemini.requests, "request")
    def test_unreadable_answer_is_an_error(self, request):
        request.return_value = http_response(
            body={"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
        )

        with self.assertRaisesRegex(TranscriptionError, "unreadable"):
            self.transcribe()

    @patch.object(gemini.requests, "request")
    def test_truncated_answer_says_the_recording_is_too_long(self, request):
        request.return_value = http_response(
            body={
                "candidates": [
                    {
                        "content": {"parts": [{"text": '{"segments": ['}]},
                        "finishReason": "MAX_TOKENS",
                    }
                ]
            }
        )

        with self.assertRaisesRegex(TranscriptionError, "too long"):
            self.transcribe()

    @patch.object(gemini.requests, "request")
    def test_blocked_prompt_is_an_error(self, request):
        request.return_value = http_response(body={"promptFeedback": {"blockReason": "OTHER"}})

        with self.assertRaisesRegex(TranscriptionError, "refused"):
            self.transcribe()

    # -- errors and retries -----------------------------------------------------

    @patch.object(gemini.requests, "request")
    def test_busy_service_is_retried_then_succeeds(self, request):
        request.side_effect = [
            http_response(429, text="quota"),
            http_response(503, text="down"),
            http_response(body=gemini_answer(GOOD_ANSWER)),
        ]

        self.assertEqual(self.transcribe().language, "Malayalam")
        self.assertEqual(request.call_count, 3)

    @patch.object(gemini.requests, "request")
    def test_gives_up_after_the_retries(self, request):
        request.return_value = http_response(429, text="quota")

        with self.assertRaisesRegex(TranscriptionError, "busy or its quota"):
            self.transcribe()

        self.assertEqual(request.call_count, 3)  # 1 try + 2 retries

    @patch.object(gemini.requests, "request")
    def test_bad_request_is_not_retried(self, request):
        request.return_value = http_response(400, text="bad audio")

        with self.assertRaisesRegex(TranscriptionError, "unsupported format"):
            self.transcribe()

        self.assertEqual(request.call_count, 1)

    @patch.object(gemini.requests, "request")
    def test_bad_credentials_do_not_leak_provider_details(self, request):
        request.return_value = http_response(403, text="API key test-key is invalid")

        with self.assertRaises(TranscriptionError) as caught:
            self.transcribe()

        self.assertNotIn("test-key", caught.exception.user_message)
        self.assertEqual(request.call_count, 1)

    @patch.object(gemini.requests, "request")
    def test_network_failure_is_retried_and_reported(self, request):
        request.side_effect = requests.ConnectionError("boom")

        with self.assertRaisesRegex(TranscriptionError, "Could not reach"):
            self.transcribe()

        self.assertEqual(request.call_count, 3)

    # -- big audio via the Files API ----------------------------------------------

    @patch.object(gemini.requests, "delete")
    @patch.object(gemini.requests, "request")
    def test_large_audio_is_uploaded_used_and_deleted(self, request, delete):
        big = b"x" * (gemini.INLINE_MAX_BYTES + 1)
        request.side_effect = [
            http_response(headers={"x-goog-upload-url": "https://upload.example/abc"}),
            http_response(
                body={"file": {"name": "files/123", "uri": "https://g/files/123", "state": "ACTIVE"}}
            ),
            http_response(body=gemini_answer(GOOD_ANSWER)),
        ]

        result = self.transcribe(audio=big)

        start, upload, generate = request.call_args_list
        self.assertTrue(start.args[1].endswith("/upload/v1beta/files"))
        self.assertEqual(start.kwargs["headers"]["X-Goog-Upload-Command"], "start")
        self.assertEqual(
            start.kwargs["headers"]["X-Goog-Upload-Header-Content-Length"], str(len(big))
        )

        self.assertEqual(upload.args[1], "https://upload.example/abc")
        self.assertEqual(upload.kwargs["data"], big)
        self.assertNotIn("x-goog-api-key", upload.kwargs["headers"])

        part = generate.kwargs["json"]["contents"][0]["parts"][0]
        self.assertEqual(
            part["fileData"], {"mimeType": "audio/mp3", "fileUri": "https://g/files/123"}
        )
        self.assertNotIn("inlineData", part)

        # The uploaded copy is removed from Google once we are done.
        self.assertTrue(delete.call_args.args[0].endswith("/v1beta/files/123"))
        self.assertEqual(result.language, "Malayalam")

    @patch.object(gemini.requests, "delete")
    @patch.object(gemini.requests, "request")
    def test_uploaded_file_is_deleted_even_when_generation_fails(self, request, delete):
        big = b"x" * (gemini.INLINE_MAX_BYTES + 1)
        request.side_effect = [
            http_response(headers={"x-goog-upload-url": "https://upload.example/abc"}),
            http_response(body={"file": {"name": "files/9", "uri": "u", "state": "ACTIVE"}}),
            http_response(400, text="bad"),
        ]

        with self.assertRaises(TranscriptionError):
            self.transcribe(audio=big)

        delete.assert_called_once()

    @patch.object(gemini.requests, "delete")
    @patch.object(gemini.requests, "request")
    def test_waits_for_the_uploaded_file_to_become_active(self, request, delete):
        big = b"x" * (gemini.INLINE_MAX_BYTES + 1)
        request.side_effect = [
            http_response(headers={"x-goog-upload-url": "https://upload.example/abc"}),
            http_response(body={"file": {"name": "files/7", "uri": "u", "state": "PROCESSING"}}),
            http_response(body={"state": "ACTIVE"}),
            http_response(body=gemini_answer(GOOD_ANSWER)),
        ]

        self.transcribe(audio=big)

        self.assertEqual(request.call_count, 4)

    @patch.object(gemini.requests, "request")
    def test_empty_audio_is_rejected_before_any_request(self, request):
        with self.assertRaises(TranscriptionError):
            self.transcribe(audio=b"")

        request.assert_not_called()


class MimeTypeTests(unittest.TestCase):
    def test_recorder_types_are_mapped_to_gemini_types(self):
        self.assertEqual(gemini_mime_type("audio/mpeg"), "audio/mp3")
        self.assertEqual(gemini_mime_type("audio/x-wav"), "audio/wav")
        self.assertEqual(gemini_mime_type("audio/x-m4a"), "audio/mp4")
        self.assertEqual(gemini_mime_type("Audio/WebM; codecs=opus"), "audio/webm")
        self.assertEqual(gemini_mime_type("audio/flac"), "audio/flac")


if __name__ == "__main__":
    unittest.main()
