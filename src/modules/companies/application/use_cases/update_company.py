from uuid import UUID

from src.modules.companies.application.interfaces.company_repository import (
    CompanyRepository,
)
from src.modules.companies.application.use_cases._guards import require_platform_admin
from src.modules.companies.domain.entities.company import Company
from src.modules.users.domain.entities.user import User

_UNSET = object()


class UpdateCompanyUseCase:

    UNSET = _UNSET

    def __init__(self, company_repository: CompanyRepository):
        self.company_repository = company_repository

    def execute(
        self,
        current_user: User,
        company_id: UUID,
        name: str | None | object = _UNSET,
        website: str | None | object = _UNSET,
    ) -> Company:
        require_platform_admin(current_user)

        update_name = name is not _UNSET
        update_website = website is not _UNSET
        if not update_name and not update_website:
            raise ValueError("At least one field must be provided.")

        new_name = None
        if update_name:
            new_name = name.strip() if isinstance(name, str) else ""
            if not new_name:
                raise ValueError("Company name cannot be empty.")

        new_website = None
        if update_website and isinstance(website, str):
            new_website = website.strip() or None

        if self.company_repository.get_by_id(company_id) is None:
            raise ValueError("Company not found.")

        return self.company_repository.update(
            company_id=company_id,
            name=new_name,
            website=new_website,
            update_website=update_website,
        )
