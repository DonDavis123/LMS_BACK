from abc import ABC, abstractmethod


class TokenCipher(ABC):
    @abstractmethod
    def encrypt(self, plain_text: str) -> str:
        pass

    @abstractmethod
    def decrypt(self, cipher_text: str) -> str:
        pass
