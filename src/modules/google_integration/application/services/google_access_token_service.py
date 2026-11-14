from uuid import UUID

from src.modules.google_integration.application.dto.oauth import GoogleAccessToken
from src.modules.google_integration.application.errors import (
    GoogleInvalidGrantError,
    GoogleNotConnectedError,
)
from src.modules.google_integration.application.interfaces.google_connection_repository import (
    GoogleConnectionRepository,
)
from src.modules.google_integration.application.interfaces.google_oauth_client import (
    GoogleOAuthClient,
)
from src.modules.google_integration.application.interfaces.token_cipher import TokenCipher


class GoogleAccessTokenService:
    """Turns a user's stored refresh token into a short-lived access token."""

    def __init__(
        self,
        connection_repository: GoogleConnectionRepository,
        oauth_client: GoogleOAuthClient,
        token_cipher: TokenCipher,
    ):
        self.connection_repository = connection_repository
        self.oauth_client = oauth_client
        self.token_cipher = token_cipher

    def get_connected_email(self, user_id: UUID) -> str | None:
        """Google account email of a connected user, or ``None``. No network call."""
        connection = self.connection_repository.get_by_user_id(user_id)
        if connection is None or not connection.is_connected:
            return None
        return connection.google_email

    def get_access_token(self, user_id: UUID) -> GoogleAccessToken:
        connection = self.connection_repository.get_by_user_id(user_id)
        if connection is None or not connection.is_connected:
            raise GoogleNotConnectedError(
                "Google account is not connected. Connect Google and try again."
            )

        refresh_token = self.token_cipher.decrypt(connection.refresh_token_encrypted)

        try:
            access_token = self.oauth_client.refresh_access_token(refresh_token)
        except GoogleInvalidGrantError as exc:
            # Revoked by the user, or expired (Google "testing" apps expire
            # refresh tokens after 7 days). Remember it so the UI can ask the
            # user to reconnect instead of failing on every call.
            connection.mark_revoked()
            self.connection_repository.save(connection)
            raise GoogleNotConnectedError(
                "Google access was revoked or has expired. Reconnect Google and try again."
            ) from exc

        return GoogleAccessToken(
            access_token=access_token,
            google_email=connection.google_email,
        )
