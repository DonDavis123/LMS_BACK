from uuid import UUID

from src.modules.companies.application.interfaces.platform_audit_log_repository import (
    PlatformAuditLogRepository,
)
from src.modules.companies.application.use_cases._guards import require_platform_admin
from src.modules.companies.domain.entities.platform_audit_action import (
    PlatformAuditAction,
)
from src.modules.companies.domain.entities.platform_audit_log import PlatformAuditLog
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.domain.entities.user import User


class GetPlatformAuditLogsUseCase:

    def __init__(self, audit_log_repository: PlatformAuditLogRepository):
        self.audit_log_repository = audit_log_repository

    def execute(
        self,
        current_user: User,
        query: ListQuery,
        company_id: UUID | None = None,
        action: PlatformAuditAction | None = None,
    ) -> PaginatedResult[PlatformAuditLog]:
        require_platform_admin(current_user)
        return self.audit_log_repository.get_all(
            query, company_id=company_id, action=action
        )
