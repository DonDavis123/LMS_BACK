from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from src.modules.leads.application.services.lead_import_pipeline import (
    READY,
    PipelineRepositories,
    build_context,
    process_rows,
    summarize,
)
from src.modules.leads.application.services.lead_import_review import (
    MAX_PROBLEMS_SHOWN,
    compact_outcome,
    fingerprint,
    importable_count,
    stored_row_problems,
    to_jsonable,
    with_server_keys,
)
from src.modules.leads.application.use_cases.lead_import_common import (
    check_settings,
    load_draft,
    require_rows,
    resolve_settings,
)
from src.modules.shared.application.tenant_context import TenantContext


class ValidateImportUseCase:
    """The full check of every row.

    The context (dropdown options, duplicate index, owners) is built once and
    the rows are then processed in memory, so a 10,000 row file costs a
    handful of queries, not one per row.
    """

    def __init__(
        self,
        job_repository,
        lead_repository,
        user_repository,
        picklist_repository,
        tenant_context: TenantContext,
    ):
        self.job_repository = job_repository
        self.lead_repository = lead_repository
        self.user_repository = user_repository
        self.picklist_repository = picklist_repository
        self.tenant_context = tenant_context

    def execute(self, job_id: UUID, mapping=None, options=None) -> dict:
        job = load_draft(self.job_repository, self.tenant_context, job_id)
        rows = require_rows(job)
        mapping_in, options_in = resolve_settings(job, mapping, options)

        check = check_settings(
            job, mapping_in, options_in, self.tenant_context, self.user_repository
        )
        stored_options = with_server_keys(check.options.to_dict(), job.options)

        if check.errors:
            # Settings that cannot be imported: keep them, drop the old check.
            stored_options.pop("last_check", None)
            self.job_repository.save_progress(
                job,
                {"mapping": check.mapping, "options": stored_options, "problems": []},
            )
            return {
                "checked": False,
                "can_import": False,
                "errors": check.errors,
                "warnings": check.warnings,
            }

        context = build_context(
            SimpleNamespace(
                headers=job.headers,
                mapping=check.mapping,
                options=check.options.to_dict(),
                rows=rows,
            ),
            self.tenant_context,
            PipelineRepositories(
                lead_repository=self.lead_repository,
                user_repository=self.user_repository,
                picklist_repository=self.picklist_repository,
            ),
        )
        outcomes = process_rows(rows, context)
        summary = to_jsonable(summarize(outcomes, context))

        owner_names = {str(owner.id): owner.name for owner in context.eligible_owners}
        stored_rows = [
            compact_outcome(outcome, owner_names)
            for outcome in outcomes
            if outcome.status != READY
        ]

        importable = importable_count(summary["counts"])
        can_import = importable > 0
        checked_at = datetime.now(timezone.utc).isoformat()
        stored_options["last_check"] = {
            "checked_at": checked_at,
            "fingerprint": fingerprint(check.mapping, stored_options),
            "summary": summary,
            "importable_rows": importable,
            "can_import": can_import,
        }
        self.job_repository.save_progress(
            job,
            {
                "mapping": check.mapping,
                "options": stored_options,
                "problems": stored_rows,
            },
        )

        first_problems = []
        for stored in stored_rows:
            first_problems.extend(stored_row_problems(stored))
            if len(first_problems) >= MAX_PROBLEMS_SHOWN:
                break

        return {
            **summary,
            "checked": True,
            "checked_at": checked_at,
            "errors": [],
            "warnings": check.warnings,
            "problems": first_problems[:MAX_PROBLEMS_SHOWN],
            "importable_rows": importable,
            "can_import": can_import,
        }
