"""Remove a recording's audio whenever its row is deleted.

Deleting a call permanently (for example when a retired user's calls are
cleaned up) cascades to its recordings without going through the delete use
case, so the audio files are removed here to avoid leaving orphans behind.
The file is only removed once the surrounding transaction has committed.
"""

import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from src.modules.calls.infrastructure.storage.django_recording_storage import (
    delete_stored_file,
)

from .models import DjangoCallRecordingModel

logger = logging.getLogger(__name__)


def _remove_file(storage_key: str) -> None:
    try:
        delete_stored_file(storage_key)
    except Exception:
        logger.exception("Could not remove call recording file %s", storage_key)


@receiver(
    post_delete,
    sender=DjangoCallRecordingModel,
    dispatch_uid="call_recording_remove_stored_file",
)
def remove_stored_file(sender, instance, **kwargs):
    storage_key = instance.storage_key
    transaction.on_commit(lambda: _remove_file(storage_key))
