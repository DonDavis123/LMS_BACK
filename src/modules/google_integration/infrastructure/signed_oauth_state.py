from uuid import UUID

from django.conf import settings
from django.core import signing

from src.modules.google_integration.application.dto.oauth import GoogleOAuthState
from src.modules.google_integration.application.errors import GoogleOAuthStateError
from src.modules.google_integration.application.interfaces.oauth_state_signer import (
    OAuthStateSigner,
)

_SALT = "google-integration.oauth-state"


class SignedOAuthStateSigner(OAuthStateSigner):
    """OAuth ``state`` signed with Django's SECRET_KEY and time-limited.

    The callback request carries no JWT (it is a browser redirect from
    Google), so this signed value is what proves who started the flow.
    """

    @staticmethod
    def _max_age() -> int:
        return int(getattr(settings, "GOOGLE_OAUTH_STATE_MAX_AGE", 600))

    def sign(self, user_id: UUID, company_id: UUID) -> str:
        return signing.dumps(
            {"u": str(user_id), "c": str(company_id)},
            salt=_SALT,
            compress=True,
        )

    def verify(self, state: str) -> GoogleOAuthState:
        if not state:
            raise GoogleOAuthStateError("Missing OAuth state.")
        try:
            payload = signing.loads(state, salt=_SALT, max_age=self._max_age())
            return GoogleOAuthState(
                user_id=UUID(payload["u"]),
                company_id=UUID(payload["c"]),
            )
        except signing.SignatureExpired as exc:
            raise GoogleOAuthStateError(
                "The Google sign-in expired. Please try connecting again."
            ) from exc
        except (signing.BadSignature, KeyError, ValueError, TypeError) as exc:
            raise GoogleOAuthStateError("Invalid OAuth state.") from exc
