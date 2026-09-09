from dataclasses import dataclass
from uuid import UUID


@dataclass
class GetAccountsDTO:
    id: UUID
    account_name: str
    phone: str | None
    website: str | None
    account_owner_id: UUID
    account_owner_name: str | None