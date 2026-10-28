from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from src.modules.leads.application.services.lead_import_processor import (
    STAGE_RUNNING,
    ImportJobNotFound,
    process_next_batch,
)
from src.modules.leads.application.services.lead_import_review import (
    client_options,
    is_draft,
)
from src.modules.leads.application.use_cases.lead_import_common import (
    ImportRequestError,
    check_settings,
    load_draft,
    not_found,
    require_rows,
    resolve_settings,
)
from src.modules.leads.application.use_cases.lead_import_run_common import (
    ImportAlreadyRunningError,
    ImportSettingsError,
)
from src.modules.shared.application.tenant_context import TenantContext


class StartLeadImportUseCase:
    """Starts a checked draft and processes its first batch at once.

    The settings are checked again here (mapping, options, owner plan), so a
    request that skipped the check screen cannot start a broken import. The
    draft is turned into a running job inside one transaction that also makes
    sure no other import of the company is running.
    """

    def __init__(
        self,
        job_repository,
        user_repository,
        tenant_context: TenantContext,
        transaction_manager,
        process_batch: Callable = process_next_batch,
    ):
        self.job_repository = job_repository
        self.user_repository = user_repository
        self.tenant_context = tenant_context
        self.transaction_manager = transaction_manager
        self.process_batch = process_batch

    def execute(self, job_id: UUID, mapping=None, options=None) -> dict:
        job = load_draft(self.job_repository, self.tenant_context, job_id)
        require_rows(job)
        mapping_in, options_in = resolve_settings(job, mapping, options)

        # Exclusions are saved on the draft by their own endpoint. A request
        # that leaves them out keeps them, rather than silently dropping them.
        saved = client_options(job.options)
        if isinstance(options_in, dict) and "exclusions" not in options_in and "exclusions" in saved:
            options_in = {**options_in, "exclusions": saved["exclusions"]}

        check = check_settings(
            job, mapping_in, options_in, self.tenant_context, self.user_repository
        )
        if check.errors:
            raise ImportSettingsError(check.errors)

        started_options = check.options.to_dict()
        started_options.update(
            {
                "stage": STAGE_RUNNING,
                "round_robin_cursor": 0,
                "converted_count": 0,
                # "Me" in the owner plan means this user in every batch.
                "started_by": str(self.tenant_context.user_id),
            }
        )

        def begin():
            locked = self.job_repository.lock_for_processing(job.id)
            if locked is None:
                raise not_found()
            if not is_draft(locked):
                raise ImportRequestError(
                    "import_already_started",
                    "This import has already been started.",
                    "Open the import history to follow it, or upload the file again "
                    "to start a new import.",
                )
            running = self.job_repository.find_running_job(exclude_job_id=locked.id)
            if running is not None:
                raise ImportAlreadyRunningError(running)

            now = datetime.now(timezone.utc)
            self.job_repository.save_progress(
                locked,
                {
                    "mapping": check.mapping,
                    "options": started_options,
                    "status": "queued",
                    "total_rows": len(locked.rows or []),
                    "processed_rows": 0,
                    "created_count": 0,
                    "updated_count": 0,
                    "skipped_count": 0,
                    "failed_count": 0,
                    "problems": [],
                    "update_snapshots": {},
                    "failure_message": "",
                    "started_at": now,
                    "finished_at": None,
                },
            )

        self.transaction_manager.execute(begin)

        # The first batch right away, so the user sees movement at once.
        try:
            progress = self.process_batch(job.id)
        except ImportJobNotFound:
            raise not_found()
        return progress.to_dict()
