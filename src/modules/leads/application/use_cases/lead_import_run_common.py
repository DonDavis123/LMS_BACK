"""Pieces shared by the use cases that run an import (start, process,
progress, cancel)."""

from __future__ import annotations

from uuid import UUID

from src.modules.leads.application.services.lead_import_processor import (
    STAGE_DRAFT,
    ImportJobNotFound,
)
from src.modules.leads.application.use_cases.lead_import_common import (
    ImportRequestError,
    not_found,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.users.domain.entities.role import UserRole


class ImportSettingsError(ImportRequestError):
    """The mapping, options or owner choices cannot be imported."""

    def __init__(self, errors: list[str]):
        first = errors[0] if errors else "The import settings are not valid."
        extra = f" (and {len(errors) - 1} more)" if len(errors) > 1 else ""
        super().__init__(
            "import_settings_invalid",
            f"{first}{extra}",
            "Fix the problems listed under 'errors' in the mapping and options "
            "steps, check the file again, then start the import.",
        )
        self.errors = list(errors)

    def to_dict(self) -> dict:
        return {**super().to_dict(), "errors": self.errors}


class ImportAlreadyRunningError(ImportRequestError):
    """Another import of the same company is still running (HTTP 409)."""

    def __init__(self, running_job):
        super().__init__(
            "import_already_running",
            "Another import is already running for your company"
            f" ('{running_job.file_name}').",
            "Wait until it finishes, or open it and cancel it, then start this "
            "import again. Only one import can run at a time.",
            status_code=409,
        )
        self.running_job_id = str(running_job.id)
        self.running_file_name = running_job.file_name

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "running_job_id": self.running_job_id,
            "running_file_name": self.running_file_name,
        }


def not_started() -> ImportRequestError:
    return ImportRequestError(
        "import_not_started",
        "This import has not been started yet.",
        "Start the import first, then follow its progress.",
    )


def load_job_light(job_repository, job_id: UUID):
    """The company's job without its large columns, or "not found"."""
    job = job_repository.get_for_company(job_id, light=True)
    if job is None:
        raise not_found()
    return job


def load_started_job(job_repository, job_id: UUID):
    """A job that has been started (not a draft). Any admin of the company may
    follow or advance it; the repository is scoped to the caller's company."""
    job = load_job_light(job_repository, job_id)
    options = job.options if isinstance(job.options, dict) else {}
    if options.get("stage") == STAGE_DRAFT:
        raise not_started()
    return job


def require_creator_or_superadmin(job, tenant_context: TenantContext) -> None:
    is_creator = str(job.created_by_id) == str(tenant_context.user_id)
    is_superadmin = str(tenant_context.role) == UserRole.SUPERADMIN.value
    if not (is_creator or is_superadmin):
        raise ImportRequestError(
            "not_your_import",
            "This import was started by another user.",
            "Only the person who uploaded the file, or a superadmin, can do this.",
            status_code=403,
        )


__all__ = [
    "ImportAlreadyRunningError",
    "ImportJobNotFound",
    "ImportSettingsError",
    "load_job_light",
    "load_started_job",
    "not_started",
    "require_creator_or_superadmin",
]
