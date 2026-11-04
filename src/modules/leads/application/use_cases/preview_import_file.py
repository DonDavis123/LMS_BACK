from uuid import UUID

from src.modules.leads.application.services.lead_import_review import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MAX_SEARCH_LENGTH,
)
from src.modules.leads.application.use_cases.lead_import_common import (
    ImportRequestError,
    load_draft,
    require_rows,
)
from src.modules.leads.application.use_cases.list_import_rows import _positive_int
from src.modules.shared.application.tenant_context import TenantContext


class PreviewImportFileUseCase:
    """Pages through the WHOLE uploaded file, exactly as it was read.

    Available as soon as the file is uploaded (the import is still a draft):
    it needs no column mapping and no check, and it shows the original cell
    text with no cleaning. Only one page is returned per call, so a
    10,000-row file costs the same as a small one. Saves nothing.
    """

    def __init__(self, job_repository, tenant_context: TenantContext):
        self.job_repository = job_repository
        self.tenant_context = tenant_context

    def execute(self, job_id: UUID, page=None, page_size=None, q=None) -> dict:
        job = load_draft(self.job_repository, self.tenant_context, job_id)  # company-scoped

        page_number = _positive_int(page, "page", 1)
        size = min(_positive_int(page_size, "page_size", DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
        search = (q or "").strip()
        if len(search) > MAX_SEARCH_LENGTH:
            raise ImportRequestError(
                "invalid_search",
                f"The search text can be at most {MAX_SEARCH_LENGTH} characters.",
                "Search for a shorter piece of text.",
            )

        rows = require_rows(job)
        needle = search.casefold()
        matching = [
            row for row in rows if not needle or self._matches(needle, row)
        ]

        total = len(matching)
        start = (page_number - 1) * size
        return {
            "headers": [str(header) for header in (job.headers or [])],
            "results": [
                {"row_number": row["row_number"], "values": row.get("values") or {}}
                for row in matching[start:start + size]
            ],
            "pagination": {
                "page": page_number,
                "page_size": size,
                "total": total,
                "total_pages": (total + size - 1) // size if total else 0,
            },
            "total_rows": len(rows),
        }

    @staticmethod
    def _matches(needle: str, row: dict) -> bool:
        if needle == str(row.get("row_number")):
            return True
        return any(
            needle in str(value).casefold()
            for value in (row.get("values") or {}).values()
            if value is not None
        )
