from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GoogleConnectionStatusDTO:
    configured: bool
    connected: bool
    status: str | None = None
    google_email: str | None = None
    connected_at: datetime | None = None
