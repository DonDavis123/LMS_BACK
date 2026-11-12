from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4

MAX_NAME_LENGTH = 255
MAX_URL_LENGTH = 2000
ALLOWED_URL_SCHEMES = ("http", "https")


def clean_document_name(name: str | None) -> str:
    cleaned = " ".join(str(name or "").split())

    if not cleaned:
        raise ValueError("Document name is required.")

    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValueError(
            f"Document name cannot be longer than {MAX_NAME_LENGTH} characters."
        )

    return cleaned


def clean_document_url(url: str | None) -> str:
    cleaned = str(url or "").strip()

    if not cleaned:
        raise ValueError("Document URL is required.")

    if len(cleaned) > MAX_URL_LENGTH:
        raise ValueError(
            f"Document URL cannot be longer than {MAX_URL_LENGTH} characters."
        )

    if any(char.isspace() for char in cleaned):
        raise ValueError("Document URL cannot contain spaces.")

    # Only web links are accepted: javascript:, data:, file: ... are refused,
    # because the link is rendered as a clickable href in the UI.
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES or not parsed.netloc:
        raise ValueError(
            "Document URL must be a valid link starting with http:// or https://."
        )

    return cleaned


@dataclass
class AccountDocument:
    """A named link to a document that belongs to one account."""

    id: UUID
    account_id: UUID
    name: str
    url: str
    created_by_id: UUID
    created_at: datetime
    modified_by_id: UUID
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        account_id: UUID,
        name: str,
        url: str,
        created_by_id: UUID,
    ) -> "AccountDocument":
        now = datetime.now(timezone.utc)

        return cls(
            id=uuid4(),
            account_id=account_id,
            name=clean_document_name(name),
            url=clean_document_url(url),
            created_by_id=created_by_id,
            created_at=now,
            modified_by_id=created_by_id,
            updated_at=now,
        )

    def update(self, *, name: str, url: str, modified_by_id: UUID) -> None:
        self.name = clean_document_name(name)
        self.url = clean_document_url(url)
        self.modified_by_id = modified_by_id
        self.updated_at = datetime.now(timezone.utc)
