from abc import ABC, abstractmethod


class EmailService(ABC):

    @abstractmethod
    def send_password_reset_email(
        self,
        recipient_email: str,
        reset_token: str,
    ) -> None:
        pass