from uuid import UUID

from src.modules.companies.application.interfaces.platform_audit_log_repository import (
    PlatformAuditLogRepository,
)
from src.modules.companies.domain.entities.platform_audit_action import (
    PlatformAuditAction,
)
from src.modules.companies.domain.entities.platform_audit_log import PlatformAuditLog
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult

from .platform_audit_log_model import PlatformAuditLogModel


class DjangoPlatformAuditLogRepository(PlatformAuditLogRepository):

    def add(self, entry: PlatformAuditLog) -> PlatformAuditLog:
        PlatformAuditLogModel.objects.create(
            id=entry.id,
            action=entry.action.value,
            actor_id=entry.actor_id,
            actor_email=entry.actor_email,
            company_id=entry.company_id,
            target_user_id=entry.target_user_id,
            target_email=entry.target_email,
            metadata=entry.metadata,
        )
        return entry

    def get_all(
        self,
        query: ListQuery,
        company_id: UUID | None = None,
        action: PlatformAuditAction | None = None,
    ) -> PaginatedResult[PlatformAuditLog]:
        queryset = PlatformAuditLogModel.objects.all()
        if company_id is not None:
            queryset = queryset.filter(company_id=company_id)
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
    def _to_domain(model: PlatformAuditLogModel) -> PlatformAuditLog:
        return PlatformAuditLog(
            id=model.id,
            action=PlatformAuditAction(model.action),
            actor_id=model.actor_id,
            actor_email=model.actor_email,
            created_at=model.created_at,
            company_id=model.company_id,
            target_user_id=model.target_user_id,
            target_email=model.target_email,
            metadata=model.metadata or {},
        )
