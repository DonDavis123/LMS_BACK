from enum import Enum


class GoogleConnectionStatus(str, Enum):
    CONNECTED = "connected"
    REVOKED = "revoked"
