from src.modules.authentication.application.interfaces.token_service import TokenService


class RefreshTokenUseCase:

    def __init__(self, token_service: TokenService):
        self.token_service = token_service

    def execute(self, refresh_token: str) -> dict:
        return self.token_service.refresh_access_token(refresh_token)