from uuid import UUID

from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from src.modules.users.application.interfaces.session_revoker import SessionRevoker


class JWTSessionRevoker(SessionRevoker):
    """Blacklists every outstanding refresh token of a user.

    Access tokens stay valid until they expire (15 minutes) but the API
    reads the user's role and active state from the database on every
    request, so they never carry stale privileges.
    """

    def revoke_all_sessions(self, user_id: UUID) -> None:
        BlacklistedToken.objects.bulk_create(
            [
                BlacklistedToken(token=token)
                for token in OutstandingToken.objects.filter(
                    user_id=user_id,
                ).exclude(blacklistedtoken__isnull=False)
            ],
            ignore_conflicts=True,
        )
