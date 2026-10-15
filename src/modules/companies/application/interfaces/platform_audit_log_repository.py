from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.companies.domain.entities.platform_audit_action import (
    PlatformAuditAction,
)
from src.modules.companies.domain.entities.platform_audit_log import PlatformAuditLog
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult


class PlatformAuditLogRepository(ABC):

    @abstractmethod
    def add(self, entry: PlatformAuditLog) -> PlatformAuditLog:
        pass

    @abstractmethod
    def get_all(
        self,
        query: ListQuery,
        company_id: UUID | None = None,
        action: PlatformAuditAction | None = None,
    ) -> PaginatedResult[PlatformAuditLog]:
        pass
