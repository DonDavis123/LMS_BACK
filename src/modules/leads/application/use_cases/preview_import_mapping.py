from types import SimpleNamespace
from uuid import UUID

from src.modules.leads.application.services.lead_import_pipeline import (
    PipelineRepositories,
    build_context,
    process_rows,
)
from src.modules.leads.application.services.lead_import_review import (
    PREVIEW_ROW_COUNT,
    row_is_blank,
    values_by_field,
    with_server_keys,
)
from src.modules.leads.application.use_cases.lead_import_common import (
    check_settings,
    load_draft,
    require_rows,
    resolve_settings,
)
from src.modules.shared.application.tenant_context import TenantContext


class PreviewImportMappingUseCase:
    """Runs the first rows through the import pipeline so the user can see
    what the mapping and options would do. Nothing but the mapping and options
    is saved, and only on the draft."""

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
        # Saved even when there are errors, so the user can come back to it.
        self.job_repository.save_progress(
            job,
            {
                "mapping": check.mapping,
                "options": with_server_keys(check.options.to_dict(), job.options),
            },
        )

        if check.errors:
            return {"errors": check.errors, "warnings": check.warnings, "rows": []}

        sample = [row for row in rows if not row_is_blank(row.get("values"))][
            :PREVIEW_ROW_COUNT
        ]
        context = build_context(
            SimpleNamespace(
                headers=job.headers,
                mapping=check.mapping,
                options=check.options.to_dict(),
                rows=sample,
            ),
            self.tenant_context,
            PipelineRepositories(
                lead_repository=self.lead_repository,
                user_repository=self.user_repository,
                picklist_repository=self.picklist_repository,
            ),
        )
        outcomes = process_rows(sample, context)
        owner_names = {str(owner.id): owner.name for owner in context.eligible_owners}

        return {
            "errors": [],
            "warnings": check.warnings,
            "rows": [
                self._row(outcome, check.mapping, owner_names) for outcome in outcomes
            ],
        }

    @staticmethod
    def _row(outcome, mapping: dict, owner_names: dict) -> dict:
        data = outcome.to_dict(include_original=False)
        payload = data.get("payload")
        owner = None
        if outcome.owner_id is not None:
            owner = {
                "id": outcome.owner_id,
                "name": owner_names.get(outcome.owner_id),
                "source": outcome.owner_source,
            }
        return {
            "row_number": outcome.row_number,
            "status": outcome.status,
            "is_converted": outcome.is_converted,
            # Tidied values when the row is valid, else what the file holds.
            "values_by_field": (
                payload
                if payload is not None
                else values_by_field(outcome.original_values, mapping)
            ),
            "owner": owner,
            "duplicate": data.get("duplicate"),
            "reason": outcome.reason,
            "problems": data["problems"],
            "warnings": data["warnings"],
        }
