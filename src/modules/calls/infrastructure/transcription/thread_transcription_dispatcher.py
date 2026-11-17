import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from django.db import connections

from src.modules.calls.application.interfaces.transcription_dispatcher import (
    TranscriptionDispatcher,
)
from src.modules.calls.application.use_cases.process_recording_transcription import (
    ProcessRecordingTranscriptionUseCase,
)

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def _shared_executor(max_workers: int) -> ThreadPoolExecutor:
    """One small pool per server process, created on first use."""
    global _executor

    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=max(1, max_workers),
                thread_name_prefix="call-transcription",
            )
        return _executor


class ThreadTranscriptionDispatcher(TranscriptionDispatcher):
    """Runs transcriptions on a small in-process thread pool.

    No extra infrastructure (no Celery / Redis), which suits a single Render
    web service. The trade-off: queued work lives in this process's memory, so
    a restart drops it. The transcript then stays PENDING / PROCESSING until it
    goes stale and the user asks again (see ``CallRecordingTranscript.is_stale``).
    When that is no longer acceptable, implement ``TranscriptionDispatcher``
    with a task queue; no use case changes.

    ``run_inline=True`` runs the job in the calling thread (tests, debugging).
    """

    def __init__(
        self,
        process_factory: Callable[[], ProcessRecordingTranscriptionUseCase],
        *,
        max_workers: int = 2,
        run_inline: bool = False,
    ):
        self._process_factory = process_factory
        self._max_workers = max_workers
        self._run_inline = run_inline

    def dispatch(self, recording_id: UUID) -> None:
        if self._run_inline:
            self._process_factory().execute(recording_id)
            return

        _shared_executor(self._max_workers).submit(self._run_in_thread, recording_id)

    def _run_in_thread(self, recording_id: UUID) -> None:
        try:
            self._process_factory().execute(recording_id)
        except Exception:  # the use case already records failures itself
            logger.exception("Transcription worker crashed for %s", recording_id)
        finally:
            # A thread owns its own database connection; do not leak it.
            connections.close_all()
