from uuid import UUID

from src.modules.authentication.application.interfaces.user_repository import (
    UserRepository,
)
from src.modules.users.infrastructure.persistence.models import User


class DjangoUserRepository(UserRepository):

    def get_by_email(self, email: str):
        return User.objects.filter(
            email=email,
        ).first()

    def get_by_id(self, user_id: UUID):
        return User.objects.filter(
            id=user_id,
        ).first()

    def save(self, user):
        django_user = User.objects.get(
            id=user.id,
        )

        django_user.password = user.password
        django_user.save(
            update_fields=["password"],
        )

        return django_user