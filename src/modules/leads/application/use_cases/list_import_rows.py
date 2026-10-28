from uuid import UUID

from src.modules.leads.application.services.lead_import_review import (
    DEFAULT_PAGE_SIZE,
    FILTER_ALL,
    MAX_PAGE_SIZE,
    MAX_SEARCH_LENGTH,
    ROW_FILTERS,
    categories,
    check_is_current,
    last_check,
    public_row,
    ready_row,
)
from src.modules.leads.application.use_cases.lead_import_common import (
    ImportRequestError,
    load_draft,
    require_rows,
)
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


class ListImportRowsUseCase:
    """Pages through the rows with the outcome of the last full check."""

    def __init__(self, job_repository, tenant_context: TenantContext):
        self.job_repository = job_repository
        self.tenant_context = tenant_context

    def execute(self, job_id: UUID, status=None, page=None, page_size=None, q=None) -> dict:
        job = load_draft(self.job_repository, self.tenant_context, job_id)

        chosen = (status or FILTER_ALL).strip().lower()
        if chosen not in ROW_FILTERS:
            raise ImportRequestError(
                "invalid_status_filter",
                f"The status filter '{chosen}' is not valid.",
                f"Use one of: {', '.join(ROW_FILTERS)}.",
            )
        page_number = _positive_int(page, "page", 1)
        size = min(_positive_int(page_size, "page_size", DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
        search = (q or "").strip()
        if len(search) > MAX_SEARCH_LENGTH:
            raise ImportRequestError(
                "invalid_search",
                f"The search text can be at most {MAX_SEARCH_LENGTH} characters.",
                "Search for a shorter piece of text.",
            )

        check = last_check(job)
        if check is None:
            raise ImportRequestError(
                "check_required",
                "Run the check first: there is no check result for this import yet.",
                "Call validate for this import, then ask for its rows.",
            )
        if not check_is_current(job):
            raise ImportRequestError(
                "check_outdated",
                "The mapping, options or exclusions changed after the last check.",
                "Call validate again, then ask for the rows.",
            )

        rows = require_rows(job)
        stored = {
            item["row_number"]: item for item in (job.problems or []) if "row_number" in item
        }
        needle = search.casefold()

        counts = {name: 0 for name in ROW_FILTERS}
        matching = []
        for row in rows:
            number = row["row_number"]
            outcome = stored.get(number) or ready_row(number)
            groups = categories(outcome["status"], bool(outcome.get("duplicate")))
            counts[FILTER_ALL] += 1
            for group in groups:
                counts[group] += 1

            if chosen != FILTER_ALL and chosen not in groups:
                continue
            if needle and not self._matches(needle, number, row.get("values")):
                continue
            matching.append((row, outcome))

        total = len(matching)
        start = (page_number - 1) * size
        results = [
            public_row(outcome, row.get("values") or {}, job.mapping or {})
            for row, outcome in matching[start:start + size]
        ]
        return {
            "results": results,
            "pagination": {
                "page": page_number,
                "page_size": size,
                "total": total,
                "total_pages": (total + size - 1) // size if total else 0,
            },
            "counts": counts,
            "checked_at": check.get("checked_at"),
        }

    @staticmethod
    def _matches(needle: str, row_number: int, values) -> bool:
        if needle == str(row_number):
            return True
        return any(
            needle in str(value).casefold()
            for value in (values or {}).values()
            if value is not None
        )
