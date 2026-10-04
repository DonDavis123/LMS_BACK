from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.users.application.dto.user_list import UserListDTO
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class GetUsersUseCase:

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(
        self,
        current_user: User,
        query: ListQuery,
    ) -> PaginatedResult[UserListDTO]:
        self._require_superadmin(current_user)

        result = self.user_repository.get_all(query)

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

    @staticmethod
    def _require_superadmin(current_user: User) -> None:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")
        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")
