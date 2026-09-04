from rest_framework_simplejwt.tokens import RefreshToken

from src.modules.authentication.application.interfaces.token_service import TokenService


class JWTTokenService(TokenService):

    def generate_tokens(self, user) -> dict:
        refresh = RefreshToken.for_user(user)

        return {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        }

    def refresh_access_token(self, refresh_token: str) -> dict:
        refresh = RefreshToken(refresh_token)

        return {
            "access_token": str(refresh.access_token),
        }