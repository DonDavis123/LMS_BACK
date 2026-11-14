from src.modules.google_integration.application.constants import CALENDAR_EVENTS_SCOPE
from src.modules.google_integration.application.dto.oauth import GoogleOAuthState
from src.modules.google_integration.application.errors import (
    GoogleOAuthError,
    GoogleOAuthStateError,
)
from src.modules.google_integration.application.interfaces.google_connection_repository import (
    GoogleConnectionRepository,
)
from src.modules.google_integration.application.interfaces.google_oauth_client import (
    GoogleOAuthClient,
)
from src.modules.google_integration.application.interfaces.token_cipher import TokenCipher
from src.modules.google_integration.domain.entities.google_connection import GoogleConnection
from src.modules.users.application.interfaces.user_repository import UserRepository


class CompleteGoogleConnectUseCase:
    """Handles Google's redirect: exchanges the code and stores the token."""

    def __init__(
        self,
        connection_repository: GoogleConnectionRepository,
        user_repository: UserRepository,
        oauth_client: GoogleOAuthClient,
        token_cipher: TokenCipher,
    ):
        self.connection_repository = connection_repository
        self.user_repository = user_repository
        self.oauth_client = oauth_client
        self.token_cipher = token_cipher

    def execute(self, code: str, state: GoogleOAuthState) -> GoogleConnection:
        if not code:
            raise GoogleOAuthError("Google did not return an authorization code.")

        user = self.user_repository.get_by_id(state.user_id)
        if user is None or not user.is_active:
            raise GoogleOAuthStateError("The user for this Google sign-in no longer exists.")

        tokens = self.oauth_client.exchange_code(code)

        if CALENDAR_EVENTS_SCOPE not in tokens.scopes:
            raise GoogleOAuthError(
                "Google Calendar permission was not granted. "
                "Allow calendar access when connecting."
            )
        if not tokens.refresh_token:
            raise GoogleOAuthError(
                "Google did not return a refresh token. Remove this app from your "
                "Google account's third-party access list and connect again."
            )

        google_email = self.oauth_client.fetch_account_email(tokens.access_token)
        encrypted = self.token_cipher.encrypt(tokens.refresh_token)
        scopes = " ".join(tokens.scopes)

        connection = self.connection_repository.get_by_user_id(state.user_id)
        if connection is None:
            connection = GoogleConnection.create(
                user_id=state.user_id,
                company_id=state.company_id,
                google_email=google_email,
                refresh_token_encrypted=encrypted,
                scopes=scopes,
            )
        else:
            connection.reconnect(
                google_email=google_email,
                refresh_token_encrypted=encrypted,
                scopes=scopes,
            )

        return self.connection_repository.save(connection)
