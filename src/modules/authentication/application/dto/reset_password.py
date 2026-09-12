from dataclasses import dataclass


@dataclass
class ResetPasswordDTO:
    token: str
    new_password: str