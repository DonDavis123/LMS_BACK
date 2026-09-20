from src.modules.authentication.application.interfaces.token_service import (
    TokenService,
)


class LogoutUserUseCase:

    def __init__(self, token_service: TokenService):
        self.token_service = token_service

    def execute(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return

        # Logout is intentionally best-effort. The presentation layer
        # clears the cookie even when the token is already expired/revoked.
        self.token_service.blacklist_refresh_token(refresh_token)
