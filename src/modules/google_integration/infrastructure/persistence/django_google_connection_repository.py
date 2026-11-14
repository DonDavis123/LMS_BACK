from uuid import UUID

from src.modules.google_integration.application.interfaces.google_connection_repository import (
    GoogleConnectionRepository,
)
from src.modules.google_integration.domain.entities.google_connection import GoogleConnection
from src.modules.google_integration.domain.enums.google_connection_status import (
    GoogleConnectionStatus,
)

from .django_google_connection_model import DjangoGoogleConnectionModel


class DjangoGoogleConnectionRepository(GoogleConnectionRepository):
    """Django persistence implementation, scoped to one company."""

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return DjangoGoogleConnectionModel.objects.filter(company_id=self._company_id)

    def get_by_user_id(self, user_id: UUID) -> GoogleConnection | None:
        model = self._base_queryset().filter(user_id=user_id).first()
        if model is None:
            return None
        return self._to_domain(model)

    def save(self, connection: GoogleConnection) -> GoogleConnection:
        model, _ = DjangoGoogleConnectionModel.objects.update_or_create(
            user_id=connection.user_id,
            defaults={
                "company_id": self._company_id,
                "google_email": connection.google_email,
                "refresh_token_encrypted": connection.refresh_token_encrypted,
                "scopes": connection.scopes,
                "status": connection.status.value,
                "connected_at": connection.connected_at,
                "updated_at": connection.updated_at,
                "revoked_at": connection.revoked_at,
            },
        )
        return self._to_domain(model)

    def delete_by_user_id(self, user_id: UUID) -> bool:
        deleted, _ = self._base_queryset().filter(user_id=user_id).delete()
        return deleted > 0

    @staticmethod
    def _to_domain(model: DjangoGoogleConnectionModel) -> GoogleConnection:
        return GoogleConnection(
            id=model.id,
            user_id=model.user_id,
            company_id=model.company_id,
            google_email=model.google_email,
            refresh_token_encrypted=model.refresh_token_encrypted,
            scopes=model.scopes,
            status=GoogleConnectionStatus(model.status),
            connected_at=model.connected_at,
            updated_at=model.updated_at,
            revoked_at=model.revoked_at,
        )
