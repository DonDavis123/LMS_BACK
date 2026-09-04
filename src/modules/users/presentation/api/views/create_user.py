from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.users.domain.entities.role import UserRole

from src.modules.users.application.use_cases.create_user import (
    CreateUserUseCase,
)

from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)

from ..serializers.create_user_serializer import CreateUserSerializer


class CreateUserView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):

        serializer = CreateUserSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        user_repository = DjangoUserRepository()

        current_user = user_repository.get_by_id(
            request.user.id
        )

        if current_user is None:
            return Response(
                {"detail": "Authenticated user not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        use_case = CreateUserUseCase(
            user_repository=user_repository,
        )

        try:
            user = use_case.execute(
                current_user=current_user,
                name=data["name"],
                email=data["email"],
                password=data["password"],
                role=UserRole(data["role"]),
            )

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role.value,
                "is_active": user.is_active,
            },
            status=status.HTTP_201_CREATED,
        )