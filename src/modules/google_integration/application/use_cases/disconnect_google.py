from uuid import UUID

from src.modules.google_integration.application.interfaces.google_connection_repository import (
    GoogleConnectionRepository,
)
from src.modules.google_integration.application.interfaces.google_oauth_client import (
    GoogleOAuthClient,
)
from src.modules.google_integration.application.interfaces.token_cipher import TokenCipher


class DisconnectGoogleUseCase:
    def __init__(
        self,
        connection_repository: GoogleConnectionRepository,
        oauth_client: GoogleOAuthClient,
        token_cipher: TokenCipher,
    ):
        self.connection_repository = connection_repository
        self.oauth_client = oauth_client
        self.token_cipher = token_cipher

    def execute(self, user_id: UUID) -> bool:
        """Revoke the token at Google and forget the connection.

        Returns ``False`` when the user had no connection.
        """
        connection = self.connection_repository.get_by_user_id(user_id)
        if connection is None:
            return False

        if connection.is_connected:
            try:
                refresh_token = self.token_cipher.decrypt(connection.refresh_token_encrypted)
            except Exception:
                refresh_token = None
            if refresh_token:
                self.oauth_client.revoke_token(refresh_token)

        return self.connection_repository.delete_by_user_id(user_id)
