from abc import ABC, abstractmethod
from uuid import UUID

from src.modules.users.domain.entities.user import User


class CurrentUserReader(ABC):
    """Reads the authenticated user's own record.

    Only ever called with the id of the authenticated user itself, so it
    works for users without a company (platform superadmins).
    """

    @abstractmethod
    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        pass
