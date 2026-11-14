from uuid import UUID

from src.modules.google_integration.application.interfaces.google_oauth_client import (
    GoogleOAuthClient,
)
from src.modules.google_integration.application.interfaces.oauth_state_signer import (
    OAuthStateSigner,
)
from src.modules.users.application.interfaces.user_repository import UserRepository


class StartGoogleConnectUseCase:
    """Builds the Google sign-in URL for the current user."""

    def __init__(
        self,
        user_repository: UserRepository,
        oauth_client: GoogleOAuthClient,
        state_signer: OAuthStateSigner,
    ):
        self.user_repository = user_repository
        self.oauth_client = oauth_client
        self.state_signer = state_signer

    def execute(self, user_id: UUID, company_id: UUID) -> str:
        user = self.user_repository.get_by_id(user_id)
        if user is None or not user.is_active:
            raise ValueError("User does not exist or is inactive.")

        state = self.state_signer.sign(user_id, company_id)
        # The user's saved Google email (if any) only pre-selects the account
        # on Google's consent screen; it is a hint, not a requirement.
        return self.oauth_client.build_authorization_url(
            state=state,
            login_hint=user.google_email,
        )
