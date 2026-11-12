"""API tests for the voice recordings of a call.

  * ``GET/POST    /api/calls/<id>/recordings/``
  * ``DELETE      /api/calls/<id>/recordings/<id>/``
  * ``GET         /api/calls/<id>/recordings/<id>/file/``

Audio is written to a throw-away MEDIA_ROOT, never to the real one.
"""

import os
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status

from src.modules.calls.infrastructure.persistence.models import (
    DjangoCallModel,
    DjangoCallRecordingModel,
)
from src.modules.calls.tests import CallApiTestCase
from src.modules.shared.tests.tenancy.factories import (
    authenticated_client,
    make_company,
    make_user,
)
from src.modules.users.infrastructure.persistence.models import User

AUDIO = b"ID3\x03\x00\x00\x00\x00\x00\x00 fake mp3 audio bytes"


def audio_file(name="call.mp3", content_type="audio/mpeg", content=AUDIO):
    return SimpleUploadedFile(name, content, content_type=content_type)


class CallRecordingApiTestCase(CallApiTestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp(prefix="lms-recordings-")
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.call_id = self._create_ok(lead_id=str(self.lead.id))["id"]

    def _url(self, *parts, call_id=None):
        suffix = "".join(f"{part}/" for part in parts)
        return f"/api/calls/{call_id or self.call_id}/recordings/{suffix}"

    def _upload(self, call_id=None, **fields):
        data = {"file": audio_file()}
        data.update(fields)
        return self.client.post(self._url(call_id=call_id), data, format="multipart")

    def _upload_ok(self, **fields):
        response = self._upload(**fields)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def _stored_files(self):
        return [
            os.path.join(folder, name)
            for folder, _, names in os.walk(self.media_root)
            for name in names
        ]


class UploadCallRecordingApiTests(CallRecordingApiTestCase):
    def test_upload_returns_the_recording(self):
        data = self._upload_ok(duration_seconds="42")

        self.assertEqual(data["call_id"], self.call_id)
        self.assertEqual(data["file_name"], "call.mp3")
        self.assertEqual(data["content_type"], "audio/mpeg")
        self.assertEqual(data["size_bytes"], len(AUDIO))
        self.assertEqual(data["duration_seconds"], 42)
        self.assertEqual(data["uploaded_by_id"], str(self.user.id))
        self.assertEqual(data["uploaded_by_name"], "Call Owner")
        self.assertEqual(
            data["file_path"],
            f"/api/calls/{self.call_id}/recordings/{data['id']}/file/",
        )
        self.assertEqual(len(self._stored_files()), 1)

    def test_upload_without_duration_is_allowed(self):
        self.assertIsNone(self._upload_ok()["duration_seconds"])

    def test_upload_is_recorded_on_the_timeline(self):
        self._upload_ok()

        response = self._timeline("calls", self.call_id)
        self.assertIn("CALL_RECORDING_ADDED", self._event_types(response))

        response = self._timeline("leads", self.lead.id)
        self.assertIn("CALL_RECORDING_ADDED", self._event_types(response))

    def test_upload_requires_a_file(self):
        response = self.client.post(self._url(), {}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data)

    def test_empty_file_is_rejected(self):
        response = self._upload(file=audio_file(content=b""))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self._stored_files(), [])

    def test_non_audio_file_is_rejected(self):
        response = self._upload(
            file=audio_file("page.html", "text/html", b"<script>alert(1)</script>")
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unsupported recording format", response.data["detail"])
        self.assertEqual(self._stored_files(), [])

    def test_file_over_the_limit_is_rejected(self):
        with override_settings(CALL_RECORDING_MAX_MB=1):
            response = self._upload(
                file=audio_file(content=b"0" * (1024 * 1024 + 1)),
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("larger than 1 MB", response.data["detail"])
        self.assertEqual(self._stored_files(), [])

    def test_invalid_duration_is_rejected(self):
        response = self._upload(duration_seconds="-5")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_planned_call_cannot_have_recordings(self):
        planned = self._create_ok(
            lead_id=str(self.lead.id),
            status="Planned",
            outcome=None,
            call_start_time=(self.now + timedelta(days=30)).isoformat(),
        )

        response = self._upload(call_id=planned["id"])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed call", response.data["detail"])

    def test_unknown_call_is_404(self):
        response = self._upload(call_id="00000000-0000-0000-0000-000000000000")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)

        self.assertIn(
            self.client.get(self._url()).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertIn(
            self._upload().status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class ListAndDownloadCallRecordingApiTests(CallRecordingApiTestCase):
    def test_list_returns_newest_first(self):
        first = self._upload_ok(file=audio_file("first.mp3"))
        second = self._upload_ok(file=audio_file("second.mp3"))

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["id"] for row in response.data["results"]],
            [second["id"], first["id"]],
        )

    def test_list_is_empty_without_recordings(self):
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_file_streams_the_audio(self):
        recording = self._upload_ok()

        response = self.client.get(self._url(recording["id"], "file"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), AUDIO)
        self.assertEqual(response["Content-Type"], "audio/mpeg")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(response["Content-Disposition"].startswith("inline"))

    def test_file_can_be_forced_to_download(self):
        recording = self._upload_ok()

        response = self.client.get(self._url(recording["id"], "file"), {"download": "1"})

        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertIn("call.mp3", response["Content-Disposition"])

    def test_file_answers_for_any_accept_header(self):
        recording = self._upload_ok()

        response = self.client.get(
            self._url(recording["id"], "file"),
            HTTP_ACCEPT="audio/webm",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_audio_file_is_404(self):
        recording = self._upload_ok()
        for path in self._stored_files():
            os.remove(path)

        response = self.client.get(self._url(recording["id"], "file"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_recording_is_only_reachable_through_its_own_call(self):
        recording = self._upload_ok()
        other_call = self._create_ok(lead_id=str(self.other_lead.id))["id"]

        response = self.client.get(
            self._url(recording["id"], "file", call_id=other_call)
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DeleteCallRecordingApiTests(CallRecordingApiTestCase):
    def test_delete_removes_row_audio_and_records_timeline(self):
        recording = self._upload_ok()

        response = self.client.delete(self._url(recording["id"]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(DjangoCallRecordingModel.objects.exists())
        self.assertEqual(self._stored_files(), [])
        self.assertEqual(self.client.get(self._url()).data["results"], [])
        self.assertIn(
            "CALL_RECORDING_DELETED",
            self._event_types(self._timeline("calls", self.call_id)),
        )

    def test_delete_unknown_recording_is_404(self):
        response = self.client.delete(
            self._url("00000000-0000-0000-0000-000000000000")
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_permanently_deleting_a_call_removes_its_audio(self):
        self._upload_ok()
        self.assertEqual(len(self._stored_files()), 1)

        with self.captureOnCommitCallbacks(execute=True):
            DjangoCallModel.objects.filter(id=self.call_id).delete()

        self.assertFalse(DjangoCallRecordingModel.objects.exists())
        self.assertEqual(self._stored_files(), [])


class CallRecordingTenantIsolationTests(CallRecordingApiTestCase):
    def setUp(self):
        super().setUp()
        self.recording = self._upload_ok()
        self.other_company_user = make_user(
            make_company("Other Company"),
            User.Role.ADMIN,
            email="other-company@example.com",
        )
        self.other_client = authenticated_client(self.other_company_user)

    def test_other_company_cannot_use_the_recording(self):
        base = f"/api/calls/{self.call_id}/recordings/"
        file_url = f"{base}{self.recording['id']}/file/"

        self.assertEqual(
            self.other_client.get(base).status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(
            self.other_client.get(file_url).status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(
            self.other_client.post(
                base, {"file": audio_file()}, format="multipart"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.other_client.delete(
                f"{base}{self.recording['id']}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertTrue(DjangoCallRecordingModel.objects.exists())
