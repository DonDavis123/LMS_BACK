from src.modules.authentication.application.interfaces.user_repository import (
    UserRepository,
)
from src.modules.users.infrastructure.persistence.models import User


class DjangoUserRepository(UserRepository):

    def get_by_email(self, email: str):
        return User.objects.filter(email=email).first()