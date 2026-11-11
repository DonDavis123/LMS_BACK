from enum import Enum


class EmailChannel(str, Enum):
    """How the email was started. More channels can be added later."""

    GMAIL_COMPOSE = "GMAIL_COMPOSE"
