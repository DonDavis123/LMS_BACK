from uuid import UUID

from src.modules.leads.application.use_cases.lead_import_common import load_draft
from src.modules.shared.application.tenant_context import TenantContext


class DiscardImportDraftUseCase:
    """Throws away an import that has not been started."""

    def __init__(self, job_repository, tenant_context: TenantContext):
        self.job_repository = job_repository
        self.tenant_context = tenant_context

    def execute(self, job_id: UUID) -> None:
        job = load_draft(self.job_repository, self.tenant_context, job_id)
        self.job_repository.delete(job)
