from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.modules.companies.domain.entities.company_status import CompanyStatus


@dataclass
class Company:
    id: UUID
    name: str
    slug: str
    status: CompanyStatus
    created_at: datetime
    updated_at: datetime
    website: str | None = None
    status_reason: str = ""
    status_changed_at: datetime | None = None
    status_changed_by_id: UUID | None = None
    created_by_id: UUID | None = None
