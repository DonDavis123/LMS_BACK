from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from src.modules.authentication.application.interfaces.token_service import (
    TokenService,
)
from src.modules.authentication.domain.exceptions import (
    InvalidRefreshTokenError,
)


class JWTTokenService(TokenService):

    def generate_tokens(self, user) -> dict:
        refresh = RefreshToken.for_user(user)

        return {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        }

    def refresh_access_token(self, refresh_token: str) -> dict:
        try:
            old_refresh = RefreshToken(refresh_token)

            user_id = old_refresh["user_id"]
            User = get_user_model()
            user = User.objects.get(id=user_id)

            # Rotate the refresh token. The old token becomes unusable.
            old_refresh.blacklist()

            new_refresh = RefreshToken.for_user(user)

            return {
                "access_token": str(new_refresh.access_token),
                "refresh_token": str(new_refresh),
            }

        except (
            TokenError,
            User.DoesNotExist,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise InvalidRefreshTokenError() from exc

    def blacklist_refresh_token(self, refresh_token: str) -> bool:
        try:
            RefreshToken(refresh_token).blacklist()
            return True
        except (
            TokenError,
            TypeError,
            ValueError,
        ):
            # Logout must remain successful even when the token
            # is already expired or blacklisted.
            return False
