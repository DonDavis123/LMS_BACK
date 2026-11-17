from abc import ABC, abstractmethod
from uuid import UUID


class TranscriptionDispatcher(ABC):
    """Runs a queued transcription outside the HTTP request.

    Transcribing takes far longer than a web request may last, so the request
    use case only queues the work and hands the recording id to a dispatcher.
    Swap the implementation (threads today) for a task queue without touching
    any use case.
    """

    @abstractmethod
    def dispatch(self, recording_id: UUID) -> None:
        pass
