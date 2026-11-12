"""Use-case tests for call recordings (no database, no file system).

The use cases only see the repository / storage / timeline interfaces, so
in-memory fakes are enough to cover the rules.
"""

import io
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from src.modules.calls.application.dto.call_recording import (
    GetCallRecordingDTO,
    UploadCallRecordingDTO,
)
from src.modules.calls.application.use_cases.delete_call_recording import (
    DeleteCallRecordingUseCase,
)
from src.modules.calls.application.use_cases.get_call_recording_file import (
    GetCallRecordingFileUseCase,
)
from src.modules.calls.application.use_cases.list_call_recordings import (
    ListCallRecordingsUseCase,
)
from src.modules.calls.application.use_cases.upload_call_recording import (
    UploadCallRecordingUseCase,
)
from src.modules.calls.domain.entities.call import Call
from src.modules.calls.domain.enums.call_outcome import CallOutcome
from src.modules.calls.domain.enums.call_status import CallStatus

MB = 1024 * 1024


class FakeTransaction:
    def execute(self, operation):
        return operation()


class FailingTransaction:
    def execute(self, operation):
        operation()
        raise RuntimeError("database went away")


class FakeTimelineRecorder:
    def __init__(self):
        self.events = []

    def record(self, *, event_type, actor_id, message, metadata=None, targets):
        self.events.append(
            {
                "event_type": event_type,
                "actor_id": actor_id,
                "message": message,
                "metadata": metadata,
                "targets": targets,
            }
        )


class FakeCallRepo:
    def __init__(self, *calls):
        self.calls = {call.id: call for call in calls}

    def get_by_id(self, call_id):
        call = self.calls.get(call_id)
        return call if call is not None and not call.is_deleted else None


class FakeRecordingRepo:
    def __init__(self):
        self.rows = {}

    def save(self, recording):
        self.rows[recording.id] = recording
        return recording

    def get_by_id(self, recording_id, call_id):
        row = self.rows.get(recording_id)
        return row if row is not None and row.call_id == call_id else None

    def get_with_relations(self, recording_id):
        row = self.rows.get(recording_id)
        return None if row is None else GetCallRecordingDTO(row, "Uploader")

    def list_by_call_id(self, call_id):
        return [
            GetCallRecordingDTO(row, "Uploader")
            for row in self.rows.values()
            if row.call_id == call_id
        ]

    def count_by_call_id(self, call_id):
        return len(self.list_by_call_id(call_id))

    def delete(self, recording_id):
        self.rows.pop(recording_id, None)


class FakeStorage:
    def __init__(self):
        self.files = {}

    def store(self, *, call_id, recording_id, extension, content):
        key = f"{call_id}/{recording_id}{extension}"
        self.files[key] = content.read()
        return key

    def open(self, storage_key):
        if storage_key not in self.files:
            raise FileNotFoundError(storage_key)
        return io.BytesIO(self.files[storage_key])

    def delete(self, storage_key):
        self.files.pop(storage_key, None)


def make_call(status=CallStatus.COMPLETED, lead_id=None, contact_id=None):
    owner_id = uuid4()
    now = datetime.now(timezone.utc)

    return Call(
        id=uuid4(),
        lead_id=lead_id or (None if contact_id else uuid4()),
        contact_id=contact_id,
        account_id=None,
        owner_id=owner_id,
        call_type="Outbound",
        outcome=CallOutcome.CONNECTED if status == CallStatus.COMPLETED else None,
        call_start_time=now,
        duration_seconds=60,
        description=None,
        entry_method="MANUAL",
        created_by_id=owner_id,
        created_at=now,
        updated_at=now,
        is_deleted=False,
        status=status,
    )


class RecordingTestCase(unittest.TestCase):
    def setUp(self):
        self.call = make_call()
        self.user_id = uuid4()
        self.call_repo = FakeCallRepo(self.call)
        self.recordings = FakeRecordingRepo()
        self.storage = FakeStorage()
        self.timeline = FakeTimelineRecorder()

    def upload_use_case(self, **kwargs):
        return UploadCallRecordingUseCase(
            self.call_repo,
            self.recordings,
            self.storage,
            self.timeline,
            kwargs.pop("transaction", FakeTransaction()),
            **kwargs,
        )

    def dto(self, **overrides):
        data = b"RIFF....WAVEfmt "
        values = {
            "call_id": self.call.id,
            "uploaded_by_id": self.user_id,
            "file_name": "call.mp3",
            "content_type": "audio/mpeg",
            "size_bytes": len(data),
            "content": io.BytesIO(data),
            "duration_seconds": 42,
        }
        values.update(overrides)
        return UploadCallRecordingDTO(**values)

    def upload(self, **overrides):
        return self.upload_use_case().execute(self.dto(**overrides))


class UploadCallRecordingTests(RecordingTestCase):
    def test_stores_audio_saves_row_and_records_timeline(self):
        result = self.upload()
        recording = result.recording

        self.assertEqual(recording.call_id, self.call.id)
        self.assertEqual(recording.uploaded_by_id, self.user_id)
        self.assertEqual(recording.file_name, "call.mp3")
        self.assertEqual(recording.content_type, "audio/mpeg")
        self.assertEqual(recording.duration_seconds, 42)
        self.assertIn(recording.storage_key, self.storage.files)
        self.assertIn(recording.id, self.recordings.rows)

        [event] = self.timeline.events
        self.assertEqual(event["event_type"], "CALL_RECORDING_ADDED")
        self.assertEqual(event["actor_id"], self.user_id)
        self.assertEqual(event["metadata"]["recording_id"], str(recording.id))
        self.assertIn(("CALL", self.call.id), event["targets"])
        self.assertIn(("LEAD", self.call.lead_id), event["targets"])

    def test_contact_call_targets_the_contact(self):
        contact_id = uuid4()
        call = make_call(contact_id=contact_id)
        self.call_repo = FakeCallRepo(call)

        self.upload(call_id=call.id)

        self.assertIn(("CONTACT", contact_id), self.timeline.events[0]["targets"])

    def test_unknown_call_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Call not found."):
            self.upload(call_id=uuid4())

        self.assertEqual(self.storage.files, {})

    def test_deleted_call_is_rejected(self):
        self.call.is_deleted = True

        with self.assertRaisesRegex(ValueError, "Call not found."):
            self.upload()

    def test_planned_or_missed_call_is_rejected(self):
        for status in (CallStatus.PLANNED, CallStatus.MISSED):
            with self.subTest(status=status):
                call = make_call(status=status)
                self.call_repo = FakeCallRepo(call)

                with self.assertRaisesRegex(ValueError, "completed call"):
                    self.upload(call_id=call.id)

        self.assertEqual(self.storage.files, {})

    def test_non_audio_file_is_rejected_before_storing(self):
        for name, content_type in (
            ("notes.pdf", "application/pdf"),
            ("page.html", "text/html"),
            ("run.exe", "application/octet-stream"),
            ("voice", ""),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "Unsupported recording format"):
                    self.upload(file_name=name, content_type=content_type)

        self.assertEqual(self.storage.files, {})
        self.assertEqual(self.timeline.events, [])

    def test_generic_content_type_falls_back_to_the_extension(self):
        result = self.upload(file_name="voice.m4a", content_type="application/octet-stream")

        self.assertEqual(result.recording.content_type, "audio/mp4")

    def test_codec_parameter_in_content_type_is_ignored(self):
        result = self.upload(file_name="rec.webm", content_type="audio/webm;codecs=opus")

        self.assertEqual(result.recording.content_type, "audio/webm")

    def test_declared_audio_type_with_a_wrong_extension_is_served_as_declared(self):
        result = self.upload(file_name="rec.bin", content_type="audio/ogg")

        self.assertEqual(result.recording.content_type, "audio/ogg")

    def test_empty_file_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            self.upload(size_bytes=0, content=io.BytesIO(b""))

    def test_file_over_the_size_limit_is_rejected(self):
        use_case = self.upload_use_case(max_size_bytes=1 * MB)

        with self.assertRaisesRegex(ValueError, "larger than 1 MB"):
            use_case.execute(self.dto(size_bytes=2 * MB))

        self.assertEqual(self.storage.files, {})

    def test_limit_of_recordings_per_call(self):
        use_case = self.upload_use_case(max_per_call=2)

        use_case.execute(self.dto(content=io.BytesIO(b"a")))
        use_case.execute(self.dto(content=io.BytesIO(b"b")))

        with self.assertRaisesRegex(ValueError, "at most 2 recordings"):
            use_case.execute(self.dto(content=io.BytesIO(b"c")))

        self.assertEqual(len(self.storage.files), 2)

    def test_invalid_duration_is_rejected(self):
        for duration in (-1, 86401, True, "5"):
            with self.subTest(duration=duration):
                with self.assertRaisesRegex(ValueError, "duration"):
                    self.upload(duration_seconds=duration)

    def test_duration_is_optional(self):
        self.assertIsNone(self.upload(duration_seconds=None).recording.duration_seconds)

    def test_file_name_is_cleaned(self):
        result = self.upload(file_name="../../etc/Client\x00 call.mp3")

        self.assertEqual(result.recording.file_name, "Client call.mp3")

    def test_audio_is_removed_again_when_saving_fails(self):
        use_case = self.upload_use_case(transaction=FailingTransaction())

        with self.assertRaises(RuntimeError):
            use_case.execute(self.dto())

        self.assertEqual(self.storage.files, {})


class ListCallRecordingsTests(RecordingTestCase):
    def test_lists_recordings_of_the_call(self):
        first = self.upload().recording

        other_call = make_call()
        self.call_repo.calls[other_call.id] = other_call
        self.upload(call_id=other_call.id)

        result = ListCallRecordingsUseCase(self.call_repo, self.recordings).execute(
            self.call.id
        )

        self.assertEqual([item.recording.id for item in result], [first.id])

    def test_unknown_call_returns_none(self):
        use_case = ListCallRecordingsUseCase(self.call_repo, self.recordings)

        self.assertIsNone(use_case.execute(uuid4()))


class GetCallRecordingFileTests(RecordingTestCase):
    def use_case(self):
        return GetCallRecordingFileUseCase(self.call_repo, self.recordings, self.storage)

    def test_returns_the_stored_audio(self):
        recording = self.upload(content=io.BytesIO(b"voice")).recording

        result = self.use_case().execute(self.call.id, recording.id)

        self.assertEqual(result.recording.id, recording.id)
        self.assertEqual(result.content.read(), b"voice")

    def test_recording_of_another_call_is_not_found(self):
        recording = self.upload().recording
        other_call = make_call()
        self.call_repo.calls[other_call.id] = other_call

        with self.assertRaisesRegex(ValueError, "Recording not found."):
            self.use_case().execute(other_call.id, recording.id)

    def test_unknown_call_or_recording_is_not_found(self):
        with self.assertRaisesRegex(ValueError, "Call not found."):
            self.use_case().execute(uuid4(), uuid4())

        with self.assertRaisesRegex(ValueError, "Recording not found."):
            self.use_case().execute(self.call.id, uuid4())

    def test_missing_audio_file_is_reported(self):
        recording = self.upload().recording
        self.storage.files.clear()

        with self.assertRaisesRegex(ValueError, "no longer available"):
            self.use_case().execute(self.call.id, recording.id)


class DeleteCallRecordingTests(RecordingTestCase):
    def use_case(self, transaction=None):
        return DeleteCallRecordingUseCase(
            self.call_repo,
            self.recordings,
            self.storage,
            self.timeline,
            transaction or FakeTransaction(),
        )

    def test_removes_row_and_audio_and_records_timeline(self):
        recording = self.upload().recording
        self.timeline.events.clear()

        self.use_case().execute(self.call.id, recording.id, current_user_id=self.user_id)

        self.assertEqual(self.recordings.rows, {})
        self.assertEqual(self.storage.files, {})

        [event] = self.timeline.events
        self.assertEqual(event["event_type"], "CALL_RECORDING_DELETED")
        self.assertEqual(event["actor_id"], self.user_id)

    def test_audio_is_kept_when_the_transaction_fails(self):
        recording = self.upload().recording

        with self.assertRaises(RuntimeError):
            self.use_case(FailingTransaction()).execute(self.call.id, recording.id)

        self.assertIn(recording.storage_key, self.storage.files)

    def test_unknown_call_or_recording_is_not_found(self):
        with self.assertRaisesRegex(ValueError, "Call not found."):
            self.use_case().execute(uuid4(), uuid4())

        with self.assertRaisesRegex(ValueError, "Recording not found."):
            self.use_case().execute(self.call.id, uuid4())


if __name__ == "__main__":
    unittest.main()
