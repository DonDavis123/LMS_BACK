"""Builds what ``process_next_batch`` needs from nothing but a job id.

A view and a future Celery task both go through ``build_import_runtime``: it
reads the job's own company and the user who started it, and returns the
company-scoped repositories. No request, no session.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.modules.accounts.infrastructure.persistence.django_account_repository import (
    DjangoAccountRepository,
)
from src.modules.contacts.infrastructure.persistence.contacts_repository import (
    DjangoContactRepository,
)
from src.modules.leads.application.services.lead_import_processor import ImportJobNotFound
from src.modules.leads.infrastructure.persistence.django_lead_import_job_model import (
    LeadImportJob,
)
from src.modules.leads.infrastructure.persistence.django_lead_import_job_repository import (
    DjangoLeadImportJobRepository,
)
from src.modules.leads.infrastructure.persistence.django_lead_repository import (
    DjangoLeadRepository,
)
from src.modules.picklists.infrastructure.persistence.django_picklist_repository import (
    DjangoPicklistRepository,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.shared.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)


@dataclass
class ImportRuntime:
    tenant_context: TenantContext
    job_repository: object
    lead_repository: object
    user_repository: object
    picklist_repository: object
    transaction_manager: object
    # Used only by converted rows (Part 10).
    account_repository: object = None
    contact_repository: object = None


def build_import_runtime(job_id: UUID) -> ImportRuntime:
    """The runtime of the job's own company, acting as the user who started it.

    "Me" in the owner plan means that user, so the batches of one import all
    resolve it the same way no matter who sends the "process" request.
    """
    stored = (
        LeadImportJob.objects.filter(id=job_id)
        .values("company_id", "created_by_id", "options")
        .first()
    )
    if stored is None or stored["company_id"] is None:
        raise ImportJobNotFound(f"Lead import {job_id} was not found.")

    company_id = stored["company_id"]
    options = stored["options"] if isinstance(stored["options"], dict) else {}
    user_id = options.get("started_by") or stored["created_by_id"]
    try:
        user_id = UUID(str(user_id))
    except ValueError:
        user_id = stored["created_by_id"]

    user_repository = DjangoUserRepository(company_id=company_id)
    user = user_repository.get_by_id(user_id)
    role = getattr(getattr(user, "role", None), "value", getattr(user, "role", "")) or ""

    return ImportRuntime(
        tenant_context=TenantContext(company_id=company_id, user_id=user_id, role=str(role)),
        job_repository=DjangoLeadImportJobRepository(company_id=company_id),
        lead_repository=DjangoLeadRepository(company_id=company_id),
        user_repository=user_repository,
        picklist_repository=DjangoPicklistRepository(company_id=company_id),
        transaction_manager=DjangoTransactionManager(),
        account_repository=DjangoAccountRepository(company_id=company_id),
        contact_repository=DjangoContactRepository(company_id=company_id),
    )


def build_conversion_repositories(company_id: UUID) -> tuple[object, object]:
    """``(account_repository, contact_repository)`` of one company, for a
    runtime that was built without them."""
    return (
        DjangoAccountRepository(company_id=company_id),
        DjangoContactRepository(company_id=company_id),
    )
