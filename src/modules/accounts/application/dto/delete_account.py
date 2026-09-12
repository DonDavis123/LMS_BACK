from dataclasses import dataclass
from uuid import UUID


@dataclass
class DeleteAccountDTO:
    account_id: UUID