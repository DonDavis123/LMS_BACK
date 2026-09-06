from django.contrib.auth import get_user_model
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
        old_refresh = RefreshToken(refresh_token)

        # Get the user associated with the refresh token
        user_id = old_refresh["user_id"]
        User = get_user_model()
        user = User.objects.get(id=user_id)

        # Blacklist the old refresh token
        old_refresh.blacklist()

        # Generate a completely new refresh token
        new_refresh = RefreshToken.for_user(user)

        return {
            "access_token": str(new_refresh.access_token),
            "refresh_token": str(new_refresh),
        }