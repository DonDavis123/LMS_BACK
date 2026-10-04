from uuid import UUID

from src.modules.users.application.dto.replacement_candidates import (
    ReplacementCandidateDTO,
)
from src.modules.users.application.interfaces.user_repository import UserRepository
from src.modules.users.domain.entities.role import UserRole
from src.modules.users.domain.entities.user import User


class GetReplacementCandidatesUseCase:
    """Active Admin/Superadmin users that can take over a retired user's data."""

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(
        self,
        current_user: User,
        user_id: UUID,
    ) -> list[ReplacementCandidateDTO]:
        self._require_superadmin(current_user)

        target_user = self.user_repository.get_by_id(user_id)
        if target_user is None:
            raise ValueError("User not found.")
        if target_user.is_deleted:
            raise ValueError("User has already been deleted.")

        candidates = self.user_repository.get_lead_owners(
            exclude_user_id=target_user.id,
        )

        return [
            ReplacementCandidateDTO(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role,
            )
            for user in candidates
        ]

    @staticmethod
    def _require_superadmin(current_user: User) -> None:
        if not current_user.is_active:
            raise ValueError("Inactive users cannot manage users.")
        if current_user.role is not UserRole.SUPERADMIN:
            raise ValueError("Only superadmins can manage users.")
