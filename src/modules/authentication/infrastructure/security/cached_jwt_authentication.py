"""JWT authentication that reads the user from the cache before the database.

``JWTAuthentication`` loads the user row on every request. This subclass keeps
the same behaviour and error responses but serves repeat requests from the
cache (Redis in production) for ``AUTH_CACHE_TTL_SECONDS`` seconds. Saving or
deleting a user clears its entry (see ``users/.../auth_cache_invalidation.py``).
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings

from src.modules.shared.infrastructure.caching import auth_cache


class CachedJWTAuthentication(JWTAuthentication):

    def get_user(self, validated_token):
        # With revocation checks on, the user row must always be fresh.
        if api_settings.CHECK_REVOKE_TOKEN or not auth_cache.is_enabled():
            return super().get_user(validated_token)

        user_id = validated_token.get(api_settings.USER_ID_CLAIM)
        if user_id is None:
            # Let the parent raise its usual "no user id in token" error.
            return super().get_user(validated_token)

        key = auth_cache.user_key(user_id)
        user = auth_cache.get(key)
        if user is not None and getattr(user, "is_active", False):
            return user

        # Miss: the parent does the query and raises for unknown / inactive
        # users, so only an active, existing user is ever cached.
        user = super().get_user(validated_token)
        auth_cache.store(key, user)
        return user
