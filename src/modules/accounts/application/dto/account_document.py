from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class AddAccountDocumentDTO:
    account_id: UUID
    name: str
    url: str


@dataclass
class UpdateAccountDocumentDTO:
    account_id: UUID
    document_id: UUID
    name: str
    url: str


@dataclass
class DeleteAccountDocumentDTO:
    account_id: UUID
    document_id: UUID


@dataclass
class GetAccountDocumentDTO:
    id: UUID
    account_id: UUID
    name: str
    url: str
    created_by_id: UUID
    created_by_name: str | None
    created_at: datetime
    modified_by_id: UUID
    updated_at: datetime
