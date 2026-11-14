from uuid import UUID

from src.modules.google_integration.application.dto.google_connection_status import (
    GoogleConnectionStatusDTO,
)
from src.modules.google_integration.application.interfaces.google_connection_repository import (
    GoogleConnectionRepository,
)
from src.modules.google_integration.application.interfaces.google_oauth_client import (
    GoogleOAuthClient,
)


class GetGoogleConnectionStatusUseCase:
    def __init__(
        self,
        connection_repository: GoogleConnectionRepository,
        oauth_client: GoogleOAuthClient,
    ):
        self.connection_repository = connection_repository
        self.oauth_client = oauth_client

    def execute(self, user_id: UUID) -> GoogleConnectionStatusDTO:
        configured = self.oauth_client.is_configured()
        connection = self.connection_repository.get_by_user_id(user_id)
        if connection is None:
            return GoogleConnectionStatusDTO(configured=configured, connected=False)

        return GoogleConnectionStatusDTO(
            configured=configured,
            connected=connection.is_connected,
            status=connection.status.value,
            google_email=connection.google_email,
            connected_at=connection.connected_at,
        )
