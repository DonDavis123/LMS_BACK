from uuid import UUID

from src.modules.leads.application.services.lead_import_processor import progress_from_job
from src.modules.leads.application.use_cases.lead_import_run_common import (
    load_started_job,
)
from src.modules.shared.application.tenant_context import TenantContext


class GetImportProgressUseCase:
    """The progress payload of an import, without processing anything."""

    def __init__(self, job_repository, tenant_context: TenantContext):
        self.job_repository = job_repository
        self.tenant_context = tenant_context

    def execute(self, job_id: UUID) -> dict:
        job = load_started_job(self.job_repository, job_id)
        return progress_from_job(job).to_dict()
