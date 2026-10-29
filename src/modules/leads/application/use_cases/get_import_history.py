from src.modules.leads.application.services.lead_import_conversion import converted_count
from src.modules.leads.application.services.lead_import_report import is_finished
from src.modules.leads.application.services.lead_import_review import DEFAULT_PAGE_SIZE
from src.modules.leads.application.services.lead_import_undo import undo_eligibility
from src.modules.leads.application.use_cases.lead_import_common import ImportRequestError
from src.modules.shared.application.dto.list_query import ListQuery
from src.modules.shared.application.tenant_context import TenantContext


def _positive_int(raw, name: str, default: int) -> int:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        value = 0
    if value < 1:
        raise ImportRequestError(
            f"invalid_{name}",
            f"{name.replace('_', ' ').capitalize()} must be a whole number of 1 or more.",
            f"Send {name}=1 or higher.",
        )
    return value


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


class GetImportHistoryUseCase:
    """The company's imports, newest first (uploads that were never started
    are not listed).

    Reads counters and the summary stored on each job only: no stored rows, no
    per-job extra query, so a page of 50 imports is one query plus the users.
    """

    def __init__(self, job_repository, tenant_context: TenantContext):
        self.job_repository = job_repository
        self.tenant_context = tenant_context

    def execute(self, page=None, page_size=None) -> dict:
        page_number = _positive_int(page, "page", 1)
        size = _positive_int(page_size, "page_size", DEFAULT_PAGE_SIZE)
        if size > ListQuery.MAX_PAGE_SIZE:
            raise ImportRequestError(
                "invalid_page_size",
                f"Page size must be {ListQuery.MAX_PAGE_SIZE} or less.",
                f"Send page_size={ListQuery.MAX_PAGE_SIZE} or lower.",
            )

        result = self.job_repository.list_for_company(
            ListQuery(page=page_number, page_size=size, sort_by=None),
            include_drafts=False,
        )
        return {
            "results": [self._row(job) for job in result.results],
            "pagination": {
                "page": result.page,
                "page_size": result.page_size,
                "total": result.total,
                "total_pages": result.total_pages,
            },
        }

    @staticmethod
    def _row(job) -> dict:
        options = job.options if isinstance(job.options, dict) else {}
        summary = options.get("report_summary")
        totals = summary.get("totals") if isinstance(summary, dict) else None
        totals = totals if isinstance(totals, dict) else {}

        # The finished report's own numbers when there are any, else the live counters.
        skipped = totals.get("skipped", job.skipped_count)
        failed = totals.get("failed", job.failed_count)
        rejected = (
            int((summary.get("rejected_rows") or {}).get("default", 0))
            if isinstance(summary, dict)
            else int(job.failed_count or 0) + int(job.skipped_count or 0)
        )

        finished = is_finished(job)
        purged = job.rows_purged_at is not None
        rejected_file = finished and not purged and rejected > 0
        results_file = finished and not purged and int(job.processed_rows or 0) > 0

        created_by = getattr(job, "created_by", None)
        undone_by = getattr(job, "undone_by", None)
        return {
            "job_id": str(job.id),
            "file_name": job.file_name,
            "status": job.status,
            "stage": options.get("stage"),
            "created_by_name": getattr(created_by, "name", None),
            "created_at": _iso(job.created_at),
            "finished_at": _iso(job.finished_at),
            "total_rows": int(job.total_rows or 0),
            "created": int(job.created_count or 0),
            "updated": int(job.updated_count or 0),
            "skipped": int(skipped or 0),
            "failed": int(failed or 0),
            "converted": converted_count(options),
            "can_undo": undo_eligibility(job).can_undo,
            "undone_at": _iso(job.undone_at),
            "undone_by_name": getattr(undone_by, "name", None),
            "files_available": rejected_file or results_file,
            "rejected_file_available": rejected_file,
            "results_file_available": results_file,
        }
