from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class LeadImportJobRepository(ABC):
    """Persistence port for lead import jobs.

    Job objects are returned as the stored record (not a domain entity) because
    the job is a persisted work queue item whose fields are saved incrementally.
    """

    @abstractmethod
    def create(
        self,
        *,
        created_by_id: UUID,
        file_name: str,
        headers: list,
        header_row: int = 1,
        sheet_name: str | None = None,
        mapping: dict | None = None,
        options: dict | None = None,
        rows: list | None = None,
        total_rows: int = 0,
    ) -> Any:
        """Create a queued job in the repository's company."""
        pass

    @abstractmethod
    def get_for_company(self, job_id: UUID) -> Any | None:
        """The job if it belongs to the repository's company, else ``None``."""
        pass

    @abstractmethod
    def lock_for_processing(self, job_id: UUID) -> Any | None:
        """Row-lock the job (SELECT ... FOR UPDATE). Must be called inside the
        caller's transaction. Returns ``None`` if not found."""
        pass

    @abstractmethod
    def save_progress(self, job: Any, fields: dict) -> Any:
        """Persist only the given fields; always refreshes ``last_activity_at``."""
        pass

    @abstractmethod
    def list_for_company(self, query: ListQuery) -> PaginatedResult[Any]:
        """Import history for the repository's company, newest first."""
        pass

    @abstractmethod
    def find_stalled(self, older_than_seconds: int, limit: int = 50) -> list[Any]:
        """Queued/processing jobs with no activity for ``older_than_seconds``.

        Not company-scoped: meant for system maintenance, not for requests.
        """
        pass

    @abstractmethod
    def purge_rows_older_than(self, days: int) -> int:
        """Clear stored rows of finished jobs older than ``days``. Counts and
        history remain. Returns the number of jobs purged. Not company-scoped."""
        pass

    @abstractmethod
    def delete(self, job: Any) -> None:
        """Delete a job of the repository's company (used to discard drafts).

        The caller decides whether the job may be deleted."""
        pass
