from abc import ABC, abstractmethod


class TokenService(ABC):

    @abstractmethod
    def generate_tokens(self, user) -> dict:
        pass

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> dict:
        pass