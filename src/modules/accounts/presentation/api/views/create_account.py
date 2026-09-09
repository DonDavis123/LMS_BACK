from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.accounts.application.dto.create_account_dto import (
    CreateAccountDTO,
)
from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_create_account_use_case,
)

from ..serializers.create_account import CreateAccountSerializer


class CreateAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        dto = CreateAccountDTO(
            account_owner_id=data.get("account_owner_id"),
            account_name=data["account_name"],
            account_site=data.get("account_site"),
            account_number=data.get("account_number"),
            account_type=data.get("account_type"),
            industry=data.get("industry"),
            annual_revenue=data.get("annual_revenue"),
            rating=data.get("rating"),
            phone=data.get("phone"),
            website=data.get("website"),
            ticker_symbol=data.get("ticker_symbol"),
            ownership=data.get("ownership"),
            employees=data.get("employees"),
            sic_code=data.get("sic_code"),
        )

        use_case = get_create_account_use_case()

        try:
            account = use_case.execute(
                data=dto,
                current_user_id=request.user.id,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "id": str(account.id),
                "message": "Account created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )