from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.modules.leads.application.services.lead_import_files import (
    FORMATS,
    FileStream,
    build_stream,
    count_rejected,
    default_format,
    download_name,
    rejected_columns,
    rejected_rows,
    results_columns,
    results_rows,
)
from src.modules.leads.application.services.lead_import_processor import is_running
from src.modules.leads.application.use_cases.lead_import_common import (
    ImportRequestError,
    not_found,
)
from src.modules.leads.application.use_cases.lead_import_run_common import (
    load_started_job,
)
from src.modules.shared.application.tenant_context import TenantContext

INCLUDE_EXCLUDED = "excluded"


@dataclass
class DownloadFile:
    file_name: str
    stream: FileStream


class ExportImportFileUseCase:
    """The two downloads of a finished import: the rows that were not added
    (to fix and upload again) and the result of every uploaded row.

    Both need the stored rows, so they are refused once the rows have been
    purged. Rows are read from the database page by page and written as they
    come, so a 10,000-row file never sits in memory as a whole.
    """

    def __init__(self, job_repository, tenant_context: TenantContext):
        self.job_repository = job_repository
        self.tenant_context = tenant_context

    # -- shared ---------------------------------------------------------

    def _load(self, job_id: UUID):
        light = load_started_job(self.job_repository, job_id)  # 404 / not started
        if light.rows_purged_at is not None:
            raise ImportRequestError(
                "files_expired",
                "The files of this import are no longer available.",
                "Files are removed some time after an import finishes. The report still "
                "shows the numbers and problems. To get the rows again, upload the "
                "original file as a new import.",
            )
        if is_running(light):
            raise ImportRequestError(
                "import_not_finished",
                "This import is still running.",
                "Wait until the import has finished, then download the file.",
            )
        job = self.job_repository.get_for_report(job_id)
        if job is None:
            raise not_found()
        return job

    @staticmethod
    def _format(requested, job) -> str:
        if requested is None or str(requested).strip() == "":
            return default_format(job.file_name)
        file_format = str(requested).strip().lower()
        if file_format not in FORMATS:
            raise ImportRequestError(
                "invalid_format",
                f"'{requested}' is not a file format we can write.",
                "Use format=csv or format=xlsx.",
            )
        return file_format

    # -- rows that were not added ---------------------------------------

    def rejected(self, job_id: UUID, file_format=None, include=None) -> DownloadFile:
        include_text = (include or "").strip().lower()
        if include_text not in ("", INCLUDE_EXCLUDED):
            raise ImportRequestError(
                "invalid_include",
                f"'{include}' is not something that can be added to this file.",
                "Use include=excluded to also list the rows you left out, or leave it out.",
            )
        job = self._load(job_id)
        file_format = self._format(file_format, job)
        include_excluded = include_text == INCLUDE_EXCLUDED

        entries = [e for e in (job.problems or []) if isinstance(e, dict)]
        if count_rejected(entries, include_excluded) == 0:
            raise ImportRequestError(
                "no_rejected_rows",
                "Good news: every row of this import was added or updated, so there "
                "is nothing to download.",
                "Open the report to see the full result of the import.",
                status_code=404,
            )

        headers = [str(h) for h in (job.headers or [])]
        columns = rejected_columns(headers)
        rows = rejected_rows(
            headers,
            entries,
            lambda: self.job_repository.iter_row_pages(job.id),
            include_excluded,
        )
        stream = build_stream(
            file_format, columns, rows, "Rejected rows", wide_columns=tuple(columns[len(headers):])
        )
        return DownloadFile(download_name(job.file_name, "rejected", file_format), stream)

    # -- one row per uploaded row ---------------------------------------

    def results(self, job_id: UUID, file_format=None) -> DownloadFile:
        job = self._load(job_id)
        file_format = self._format(file_format, job)

        entries = [e for e in (job.problems or []) if isinstance(e, dict)]
        options = job.options if isinstance(job.options, dict) else {}
        headers = [str(h) for h in (job.headers or [])]
        columns = results_columns(headers)
        rows = results_rows(
            headers, entries, self.job_repository.iter_row_pages(job.id), options
        )
        stream = build_stream(
            file_format, columns, rows, "Results", wide_columns=(columns[len(headers) + 1],)
        )
        return DownloadFile(download_name(job.file_name, "results", file_format), stream)
