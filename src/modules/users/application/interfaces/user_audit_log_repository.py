from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.domain.entities.user_audit_action import UserAuditAction
from src.modules.users.domain.entities.user_audit_log import UserAuditLog


class UserAuditLogRepository(ABC):

    @abstractmethod
    def add(self, entry: UserAuditLog) -> UserAuditLog:
        pass

    @abstractmethod
    def get_all(
        self,
        query: ListQuery,
        target_user_id: UUID | None = None,
        action: UserAuditAction | None = None,
    ) -> PaginatedResult[UserAuditLog]:
        """Newest first."""
        pass
