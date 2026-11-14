class GoogleIntegrationNotConfiguredError(Exception):
    """The server is missing Google OAuth settings (client id, secret, ...)."""


class GoogleNotConnectedError(ValueError):
    """The user has no usable Google connection (never connected or revoked)."""


class GoogleOAuthStateError(ValueError):
    """The OAuth ``state`` is missing, forged or expired."""


class GoogleOAuthError(ValueError):
    """Google refused or failed an OAuth request."""


class GoogleInvalidGrantError(GoogleOAuthError):
    """The refresh token is no longer valid (revoked or expired)."""
