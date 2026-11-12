import logging
from typing import BinaryIO
from uuid import UUID

from django.core.files import File
from django.core.files.storage import storages

from src.modules.calls.application.interfaces.recording_storage import (
    RecordingStorage,
)
from src.modules.calls.domain.entities.call_recording import ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)

STORAGE_PREFIX = "call_recordings"
FALLBACK_EXTENSION = ".bin"

# Name of the entry in settings.STORAGES that holds the recordings.
STORAGE_ALIAS = "call_recordings"


def _storage():
    return storages[STORAGE_ALIAS]


def delete_stored_file(storage_key: str) -> None:
    """Remove one stored file; a file that is already gone is fine."""
    if storage_key:
        _storage().delete(storage_key)


class DjangoRecordingStorage(RecordingStorage):
    """Keeps recordings in the ``call_recordings`` entry of ``settings.STORAGES``.

    That is a private Supabase Storage bucket when ``SUPABASE_STORAGE_BUCKET``
    is set, otherwise the ``MEDIA_ROOT`` folder. Files are only ever served
    through the authenticated recording endpoint, never from a public URL.
    """

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def store(
        self,
        *,
        call_id: UUID,
        recording_id: UUID,
        extension: str,
        content: BinaryIO,
    ) -> str:
        # The client chose the name, so only a known audio extension is kept.
        safe_extension = extension if extension in ALLOWED_EXTENSIONS else FALLBACK_EXTENSION
        key = (
            f"{STORAGE_PREFIX}/{self._company_id}/{call_id}/"
            f"{recording_id}{safe_extension}"
        )

        if hasattr(content, "seek"):
            content.seek(0)

        file = content if isinstance(content, File) else File(content)

        return _storage().save(key, file)

    def open(self, storage_key: str) -> BinaryIO:
        return _storage().open(storage_key, "rb")

    def delete(self, storage_key: str) -> None:
        delete_stored_file(storage_key)
