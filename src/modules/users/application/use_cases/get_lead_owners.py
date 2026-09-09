from src.modules.users.application.dto.lead_owners import (
    LeadOwnerResponseDTO,
)
from src.modules.users.application.interfaces.user_repository import (
    UserRepository,
)


class GetLeadOwnersUseCase:

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def execute(self) -> list[LeadOwnerResponseDTO]:

        users = self.user_repository.get_lead_owners()

        return [
            LeadOwnerResponseDTO(
                id=user.id,
                name=user.name,
                email=user.email,
            )
            for user in users
        ]