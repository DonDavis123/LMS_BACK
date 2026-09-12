from abc import ABC, abstractmethod
from uuid import UUID


class PasswordResetTokenService(ABC):

    @abstractmethod
    def generate_token(self, user_id: UUID) -> str:
        """
        Generate and persist a password reset token
        for the given user and return the raw token.
        """
        pass

    @abstractmethod
    def validate_token(self, token: str) -> UUID | None:
        """
        Validate the reset token.

        Returns:
            The associated user ID if the token is valid.
            None if the token is invalid, expired, or already used.
        """
        pass

    @abstractmethod
    def consume_token(self, token: str) -> None:
        """
        Mark the reset token as used so it cannot
        be used again.
        """
        pass