from abc import ABC, abstractmethod


class TokenService(ABC):

    @abstractmethod
    def generate_tokens(self, user) -> dict:
        pass