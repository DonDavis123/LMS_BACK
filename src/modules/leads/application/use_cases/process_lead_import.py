from typing import Callable
from uuid import UUID

from src.modules.leads.application.services.lead_import_processor import (
    ImportJobNotFound,
    process_next_batch,
)
from src.modules.leads.application.use_cases.lead_import_common import (
    ImportRequestError,
    not_found,
)
from src.modules.leads.application.use_cases.lead_import_run_common import (
    load_started_job,
)
from src.modules.shared.application.tenant_context import TenantContext


def parse_expected_rows(raw):
    """The optional ``processed_rows`` the client last saw (a whole number)."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        raw = "x"
    try:
        value = int(str(raw).strip())
    except ValueError:
        value = -1
    if value < 0:
        raise ImportRequestError(
            "invalid_processed_rows",
            "'processed_rows' must be a whole number, 0 or more.",
            "Send the processed_rows value from the last progress response, or leave it out.",
        )
    return value


class ProcessLeadImportUseCase:
    """Advances a started import by one batch and returns its progress.

    Any admin of the company may call it. The company check happens here, on
    the company-scoped repository; ``process_next_batch`` itself only knows the
    job id.
    """

    def __init__(
        self,
        job_repository,
        tenant_context: TenantContext,
        process_batch: Callable = process_next_batch,
    ):
        self.job_repository = job_repository
        self.tenant_context = tenant_context
        self.process_batch = process_batch

    def execute(self, job_id: UUID, processed_rows=None) -> dict:
        expected = parse_expected_rows(processed_rows)
        load_started_job(self.job_repository, job_id)
        try:
            progress = self.process_batch(job_id, expected_processed_rows=expected)
        except ImportJobNotFound:
            raise not_found()
        return progress.to_dict()
