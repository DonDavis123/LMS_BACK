from uuid import UUID

from src.modules.leads.application.services.lead_import_report import (
    build_report,
    build_report_summary,
)
from src.modules.leads.application.use_cases.lead_import_common import not_found
from src.modules.leads.application.use_cases.lead_import_run_common import (
    load_started_job,
)
from src.modules.shared.application.tenant_context import TenantContext


class GetImportReportUseCase:
    """The detailed report of a started import (finished, cancelled, failed or
    still running).

    A finished import carries its report in ``options["report_summary"]``
    (written once by ``finalize_job``), so the report needs no stored rows and
    still works after they have been purged. Only an import that was never
    finalised (still running, or finished before this feature existed) is
    summarised on the spot from its stored problems.
    """

    def __init__(self, job_repository, user_repository, tenant_context: TenantContext):
        self.job_repository = job_repository
        self.user_repository = user_repository
        self.tenant_context = tenant_context

    def execute(self, job_id: UUID) -> dict:
        job = load_started_job(self.job_repository, job_id)  # company-scoped, light
        options = job.options if isinstance(job.options, dict) else {}
        stored = options.get("report_summary")

        if isinstance(stored, dict) and stored.get("totals"):
            summary = stored
        else:
            full = self.job_repository.get_for_report(job_id)
            if full is None:
                raise not_found()
            job = full
            summary = build_report_summary(full)

        creator = self.user_repository.get_by_id(job.created_by_id)
        return build_report(job, summary, getattr(creator, "name", None))
