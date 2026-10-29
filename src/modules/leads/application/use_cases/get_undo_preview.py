from typing import Callable
from uuid import UUID

from src.modules.leads.application.services.lead_import_undo import (
    preview_payload,
    run_undo,
    undo_eligibility,
)
from src.modules.leads.application.use_cases.lead_import_run_common import (
    load_started_job,
)
from src.modules.shared.application.tenant_context import TenantContext


class GetUndoPreviewUseCase:
    """Tells the user exactly what an undo would do, without doing anything.

    It runs the very same passes as the real undo with ``dry_run=True`` (reads
    only), so the numbers shown are the numbers the undo will act on, apart from
    changes made in the seconds between the preview and the confirmation (the
    undo checks every record again, inside its own transaction).

    An import that cannot be undone is not an error here: the answer is 200 with
    ``can_undo: false`` and the reason, so the screen can explain it.
    """

    def __init__(
        self,
        job_repository,
        tenant_context: TenantContext,
        store_factory: Callable[[UUID], object],
    ):
        self.job_repository = job_repository
        self.tenant_context = tenant_context
        self.store_factory = store_factory

    def execute(self, job_id: UUID) -> dict:
        job = load_started_job(self.job_repository, job_id)  # company-scoped, light
        eligibility = undo_eligibility(job)
        if not eligibility.can_undo:
            return preview_payload(job, None, eligibility)

        store = self.store_factory(job_id)
        run = run_undo(job, store, dry_run=True, snapshots=store.update_snapshots())
        return preview_payload(job, run, eligibility)
