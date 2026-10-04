from uuid import UUID

from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.application.interfaces.user_audit_log_repository import (
    UserAuditLogRepository,
)
from src.modules.users.domain.entities.user_audit_action import UserAuditAction
from src.modules.users.domain.entities.user_audit_log import UserAuditLog

from .user_audit_log_model import DjangoUserAuditLogModel


class DjangoUserAuditLogRepository(UserAuditLogRepository):

    def add(self, entry: UserAuditLog) -> UserAuditLog:
        DjangoUserAuditLogModel.objects.create(
            id=entry.id,
            action=entry.action.value,
            actor_id=entry.actor_id,
            actor_email=entry.actor_email,
            target_user_id=entry.target_user_id,
            target_email=entry.target_email,
            metadata=entry.metadata,
            created_at=entry.created_at,
        )
        return entry

    def get_all(
        self,
        query: ListQuery,
        target_user_id: UUID | None = None,
        action: UserAuditAction | None = None,
    ) -> PaginatedResult[UserAuditLog]:
        queryset = DjangoUserAuditLogModel.objects.all()

        if target_user_id is not None:
            queryset = queryset.filter(target_user_id=target_user_id)
        if action is not None:
            queryset = queryset.filter(action=action.value)

        total = queryset.count()
        offset = (query.page - 1) * query.page_size
        models = queryset.order_by("-created_at", "-id")[
            offset:offset + query.page_size
        ]

        return PaginatedResult(
            results=[self._to_domain(model) for model in models],
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    @staticmethod
    def _to_domain(model: DjangoUserAuditLogModel) -> UserAuditLog:
        return UserAuditLog(
            id=model.id,
            action=UserAuditAction(model.action),
            actor_id=model.actor_id,
            actor_email=model.actor_email,
            target_user_id=model.target_user_id,
            target_email=model.target_email,
            created_at=model.created_at,
            metadata=model.metadata or {},
        )
