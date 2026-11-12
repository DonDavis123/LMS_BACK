"""Use-case tests for the overall recording storage limit (no database).

The storage bucket is shared by every company, so the upload use case checks
the total size of all recordings before it stores a new one.
"""

import unittest

from src.modules.calls.application.tests_recordings import (
    FakeRecordingRepo,
    MB,
    RecordingTestCase,
)
from src.modules.calls.application.use_cases.upload_call_recording import (
    UploadCallRecordingUseCase,
)


class QuotaRecordingRepo(FakeRecordingRepo):
    """Reports a fixed amount of already used storage, like the shared bucket."""

    def __init__(self, used_bytes=0):
        super().__init__()
        self.used_bytes = used_bytes

    def total_size_bytes(self):
        return self.used_bytes + sum(row.size_bytes for row in self.rows.values())


class RecordingStorageLimitTests(RecordingTestCase):
    def setUp(self):
        super().setUp()
        self.recordings = QuotaRecordingRepo(used_bytes=10 * MB)

    def upload_with_limit(self, limit_bytes, **overrides):
        return self.upload_use_case(max_total_bytes=limit_bytes).execute(
            self.dto(**overrides)
        )

    def test_upload_is_allowed_while_there_is_room(self):
        result = self.upload_with_limit(11 * MB, size_bytes=1 * MB)

        self.assertIn(result.recording.storage_key, self.storage.files)

    def test_upload_that_would_exceed_the_limit_is_refused_before_storing(self):
        with self.assertRaisesRegex(ValueError, "storage is full"):
            self.upload_with_limit(10 * MB, size_bytes=1 * MB)

        self.assertEqual(self.storage.files, {})
        self.assertEqual(self.recordings.rows, {})
        self.assertEqual(self.timeline.events, [])

    def test_file_that_exactly_fills_the_limit_is_allowed(self):
        self.upload_with_limit(11 * MB, size_bytes=1 * MB)

        self.assertEqual(len(self.storage.files), 1)

    def test_storage_fills_up_across_uploads(self):
        self.upload_with_limit(12 * MB, size_bytes=1 * MB)
        self.upload_with_limit(12 * MB, size_bytes=1 * MB)

        with self.assertRaisesRegex(ValueError, "storage is full"):
            self.upload_with_limit(12 * MB, size_bytes=1 * MB)

    def test_no_limit_means_no_check(self):
        result = self.upload_with_limit(None, size_bytes=1 * MB)

        self.assertIn(result.recording.storage_key, self.storage.files)

    def test_default_has_no_overall_limit(self):
        use_case = self.upload_use_case()

        self.assertIsNone(use_case.max_total_bytes)
        self.assertIsInstance(use_case, UploadCallRecordingUseCase)


if __name__ == "__main__":
    unittest.main()
