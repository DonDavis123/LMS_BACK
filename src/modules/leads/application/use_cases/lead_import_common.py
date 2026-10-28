"""Pieces shared by the lead import review use cases."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from uuid import UUID

from src.modules.leads.application.services.lead_import_mapping import (
    mapping_to_columns,
    validate_mapping,
)
from src.modules.leads.application.services.lead_import_options import (
    ImportOptions,
    validate_options,
)
from src.modules.leads.application.services.lead_import_owners import (
    OwnerPlan,
    load_eligible_owners,
    validate_plan,
)
from src.modules.leads.application.services.lead_import_review import (
    client_options,
    is_draft,
    sanitize_mapping,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.users.domain.entities.role import UserRole


class ImportRequestError(Exception):
    """A request problem answered as ``{detail, code, how_to_fix}``."""

    def __init__(self, code: str, message: str, how_to_fix: str = "", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.how_to_fix = how_to_fix
        self.status_code = status_code

    def to_dict(self) -> dict:
        return {"code": self.code, "detail": self.message, "how_to_fix": self.how_to_fix}


def not_found() -> ImportRequestError:
    return ImportRequestError(
        "import_not_found",
        "This import was not found.",
        "Upload your file again to start a new import.",
        status_code=404,
    )


def load_draft(job_repository, tenant_context: TenantContext, job_id: UUID):
    """The caller's own draft job (or any draft for a SUPERADMIN).

    The repository is scoped to the caller's company, so a job of another
    company is simply "not found".
    """
    job = job_repository.get_for_company(job_id)
    if job is None:
        raise not_found()

    is_creator = str(job.created_by_id) == str(tenant_context.user_id)
    is_superadmin = str(tenant_context.role) == UserRole.SUPERADMIN.value
    if not (is_creator or is_superadmin):
        raise ImportRequestError(
            "not_your_import",
            "This import was started by another user.",
            "Only the person who uploaded the file, or a superadmin, can change it. "
            "Upload the file again to start your own import.",
            status_code=403,
        )

    if not is_draft(job):
        raise ImportRequestError(
            "import_already_started",
            "This import has already been started, so it can no longer be changed.",
            "Open the import history to follow it, or upload the file again to start a new import.",
        )
    return job


def require_rows(job) -> list:
    if job.rows is None:
        raise ImportRequestError(
            "import_rows_unavailable",
            "The rows of this import are no longer stored.",
            "Upload the file again to start a new import.",
        )
    return job.rows


@dataclass
class SettingsCheck:
    options: ImportOptions
    mapping: dict  # sanitized, safe to store
    errors: list = dataclass_field(default_factory=list)
    warnings: list = dataclass_field(default_factory=list)


def resolve_settings(job, mapping, options):
    """The mapping and options to use: the request's, or what is stored."""
    if mapping is not None and not isinstance(mapping, dict):
        raise ImportRequestError(
            "invalid_request",
            "The mapping must be an object like {\"Column name\": \"field_key\"}.",
            "Send the mapping as {column name: field key}, using \"__ignore__\" for unwanted columns.",
        )
    if options is not None and not isinstance(options, dict):
        raise ImportRequestError(
            "invalid_request",
            "The options must be an object.",
            "Send the options as a JSON object, or leave them out to use the saved ones.",
        )
    return (
        mapping if mapping is not None else dict(job.mapping or {}),
        options if options is not None else client_options(job.options),
    )


def check_settings(job, mapping, options, tenant_context, user_repository) -> SettingsCheck:
    """Mapping, options and owner plan checked together (no row is read)."""
    parsed = ImportOptions.from_dict(options)
    headers = list(job.headers or [])
    clean_mapping = sanitize_mapping(mapping, headers)

    mapping_check = validate_mapping(mapping, headers, parsed)
    errors = list(mapping_check.errors)
    errors.extend(validate_options(parsed, headers))

    eligible = load_eligible_owners(tenant_context, user_repository)
    errors.extend(
        validate_plan(
            OwnerPlan.from_dict(parsed.owner_plan),
            eligible,
            "owner" in mapping_to_columns(clean_mapping),
            tenant_context.user_id,
        )
    )
    return SettingsCheck(
        options=parsed,
        mapping=clean_mapping,
        errors=errors,
        warnings=list(mapping_check.warnings),
    )
