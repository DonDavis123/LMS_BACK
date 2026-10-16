from uuid import UUID

from src.modules.companies.application.interfaces.company_repository import (
    CompanyRepository,
)
from src.modules.companies.application.interfaces.platform_audit_log_repository import (
    PlatformAuditLogRepository,
)
from src.modules.companies.domain.entities.platform_audit_action import (
    PlatformAuditAction,
)
from src.modules.companies.domain.entities.platform_audit_log import PlatformAuditLog
from src.modules.companies.application.use_cases._guards import require_platform_admin
from src.modules.companies.domain.entities.company import Company
from src.modules.shared.application.interfaces.transaction_manager import (
    TransactionManager,
)
from src.modules.users.domain.entities.user import User

_UNSET = object()


class UpdateCompanyUseCase:

    UNSET = _UNSET

    def __init__(
        self,
        company_repository: CompanyRepository,
        platform_audit_log_repository: PlatformAuditLogRepository,
        transaction_manager: TransactionManager,
    ):
        self.company_repository = company_repository
        self.platform_audit_log_repository = platform_audit_log_repository
        self.transaction_manager = transaction_manager

    def execute(
        self,
        current_user: User,
        company_id: UUID,
        name: str | None | object = _UNSET,
        website: str | None | object = _UNSET,
    ) -> Company:
        require_platform_admin(current_user)

        update_name = name is not _UNSET
        update_website = website is not _UNSET
        if not update_name and not update_website:
            raise ValueError("At least one field must be provided.")

        new_name = None
        if update_name:
            new_name = name.strip() if isinstance(name, str) else ""
            if not new_name:
                raise ValueError("Company name cannot be empty.")

        new_website = None
        if update_website and isinstance(website, str):
            new_website = website.strip() or None

        company = self.company_repository.get_by_id(company_id)
        if company is None:
            raise ValueError("Company not found.")

        # Only fields whose value really changes are written and audited, so
        # saving an unchanged form does not leave a misleading audit entry.
        changed_fields = []
        if update_name and new_name != company.name:
            changed_fields.append("name")
        if update_website and new_website != (company.website or None):
            changed_fields.append("website")

        if not changed_fields:
            return company

        def update() -> Company:
            updated = self.company_repository.update(
                company_id=company_id,
                name=new_name if "name" in changed_fields else None,
                website=new_website,
                update_website="website" in changed_fields,
            )
            self.platform_audit_log_repository.add(
                PlatformAuditLog.create(
                    action=PlatformAuditAction.COMPANY_UPDATED,
                    actor=current_user,
                    company_id=company_id,
                    metadata={"changed_fields": changed_fields},
                )
            )
            return updated

        return self.transaction_manager.execute(update)
