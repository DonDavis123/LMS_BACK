from uuid import UUID

from src.modules.companies.application.interfaces.company_repository import (
    CompanyRepository,
)
from src.modules.companies.application.use_cases._guards import require_platform_admin
from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.application.dto.user_list import UserListDTO
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.user import User
from collections.abc import Callable


class GetCompanyUsersUseCase:

    def __init__(
        self,
        company_repository: CompanyRepository,
        user_repository_factory: Callable[[UUID], UserRepository],
    ):
        self.company_repository = company_repository
        self.user_repository_factory = user_repository_factory

    def execute(
        self,
        current_user: User,
        company_id: UUID,
        query: ListQuery,
    ) -> PaginatedResult[UserListDTO]:
        require_platform_admin(current_user)

        if self.company_repository.get_by_id(company_id) is None:
            raise ValueError("Company not found.")

        result = self.user_repository_factory(company_id).get_all(query)

        return PaginatedResult(
            results=[
                UserListDTO(
                    id=user.id,
                    name=user.name,
                    email=user.email,
                    role=user.role,
                    is_active=user.is_active,
                    created_at=user.created_at,
                )
                for user in result.results
            ],
            page=result.page,
            page_size=result.page_size,
            total=result.total,
        )
