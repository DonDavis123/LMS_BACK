from uuid import UUID

from src.modules.users.application.interfaces.current_user_reader import (
    CurrentUserReader,
)
from src.modules.users.domain.entities.user import User

from .models import User as DjangoUser
from .user_repository import DjangoUserRepository


class DjangoCurrentUserReader(CurrentUserReader):
    """Deliberately NOT company-scoped: GET /users/me/ must also work for
    platform superadmins, who have no company. It can only return the row
    whose id it is given, and the view always passes ``request.user.id``.
    Never use it to look up other users.
    """

    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        try:
            django_user = DjangoUser.objects.get(id=user_id)
        except DjangoUser.DoesNotExist:
            return None

        return DjangoUserRepository._to_domain(django_user)


# The scoped repository also satisfies this read-only contract.
CurrentUserReader.register(DjangoUserRepository)
