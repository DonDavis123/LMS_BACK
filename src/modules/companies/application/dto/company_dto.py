from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from src.modules.companies.domain.entities.company_status import CompanyStatus


@dataclass(frozen=True)
class CompanyListDTO:
    id: UUID
    name: str
    slug: str
    website: str | None
    status: CompanyStatus
    created_at: datetime
    users_count: int


@dataclass(frozen=True)
class CompanyAdminDTO:
    id: UUID
    name: str
    email: str
    is_active: bool


@dataclass(frozen=True)
class CompanyDetailDTO:
    id: UUID
    name: str
    slug: str
    website: str | None
    status: CompanyStatus
    status_reason: str
    status_changed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    users_count: int
    superadmins: list[CompanyAdminDTO] = field(default_factory=list)


@dataclass(frozen=True)
class CreateCompanyDTO:
    company_name: str
    admin_name: str
    admin_email: str
    admin_password: str
    website: str | None = None


@dataclass(frozen=True)
class RecentCompanyDTO:
    id: UUID
    name: str
    status: CompanyStatus
    created_at: datetime


@dataclass(frozen=True)
class MonthlyCountDTO:
    month: str  # "YYYY-MM"
    count: int


@dataclass(frozen=True)
class RoleCountDTO:
    role: str
    count: int


@dataclass(frozen=True)
class TopCompanyDTO:
    id: UUID
    name: str
    status: CompanyStatus
    users_count: int


@dataclass(frozen=True)
class PlatformOverviewDTO:
    companies_total: int
    companies_active: int
    companies_onboarding: int
    companies_suspended: int
    users_total: int
    users_active: int
    recent_companies: list[RecentCompanyDTO] = field(default_factory=list)
    companies_growth: list[MonthlyCountDTO] = field(default_factory=list)
    users_by_role: list[RoleCountDTO] = field(default_factory=list)
    top_companies: list[TopCompanyDTO] = field(default_factory=list)
