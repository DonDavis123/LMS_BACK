from datetime import datetime, timezone
from uuid import UUID

from src.modules.leads.application.services.lead_import_processor import (
    STAGE_CANCELLED,
    STATUS_COMPLETED,
    finish_hook,
    is_running,
    progress_from_job,
)
from src.modules.leads.application.use_cases.lead_import_common import not_found
from src.modules.leads.application.use_cases.lead_import_run_common import (
    load_started_job,
    require_creator_or_superadmin,
)
from src.modules.shared.application.tenant_context import TenantContext


class CancelLeadImportUseCase:
    """Stops a running import after the batch that is being processed.

    Taking the job lock waits for a batch in progress to finish, so a cancel
    never cuts a batch in half. The job then ends as ``completed`` with
    ``options["stage"] == "cancelled"``: the leads already added are kept, the
    counts stay, and the import can still be reported and undone. Cancelling a
    job that already ended changes nothing.
    """

    def __init__(
        self,
        job_repository,
        user_repository,
        tenant_context: TenantContext,
        transaction_manager,
    ):
        self.job_repository = job_repository
        self.user_repository = user_repository
        self.tenant_context = tenant_context
        self.transaction_manager = transaction_manager

    def execute(self, job_id: UUID) -> dict:
        job = load_started_job(self.job_repository, job_id)
        require_creator_or_superadmin(job, self.tenant_context)

        user = self.user_repository.get_by_id(self.tenant_context.user_id)
        name = getattr(user, "name", None)

        def cancel():
            locked = self.job_repository.lock_for_processing(job_id)
            if locked is None:
                raise not_found()
            if not is_running(locked):
                return locked, False
            options = dict(locked.options or {})
            options["stage"] = STAGE_CANCELLED
            options["cancelled_by"] = str(self.tenant_context.user_id)
            if name:
                options["cancelled_by_name"] = name
            self.job_repository.save_progress(
                locked,
                {
                    "status": STATUS_COMPLETED,
                    "finished_at": datetime.now(timezone.utc),
                    "options": options,
                },
            )
            return locked, True

        locked, cancelled = self.transaction_manager.execute(cancel)
        if cancelled:
            finish_hook(locked, None)
        return progress_from_job(locked).to_dict()
