class AuthenticationError(Exception):
    """Base exception for authentication failures."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when the supplied credentials are invalid."""


class InactiveUserError(AuthenticationError):
    """Raised when an inactive user attempts to authenticate."""


class InvalidRefreshTokenError(AuthenticationError):
    """Raised when a refresh token is invalid, expired, or revoked."""
